import re
import json
from huggingface_hub import InferenceClient
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

torch.random.manual_seed(0)
import socket

client = InferenceClient(api_key="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")


def return_array(category, text):
    category_sizes = {'depression': 9, 'anxiety': 7, 'adhd': 6, 'schizophrenia': 7, 'insomnia': 6}

    match = re.search(r"\[(.*?)\]", text)
    if match:
        boolean_array = [
            item.strip().lower() == "true" for item in match.group(1).split(",")
        ]
        return boolean_array
    else:
        boolean_array = [False for _ in range(category_sizes[category])]
        return boolean_array


def prompt_llm_inference(category, user_prompt):
    with open("./prompts.txt", "r") as f:
        loaded_data = json.load(f)
    final_prompt = loaded_data[category] + f'\nSentence to Evaluate: "{user_prompt}"'
    messages = [
        {"role": "user", "content": final_prompt},
    ]
    stream = client.chat.completions.create(
        model="microsoft/Phi-3.5-mini-instruct",
        messages=messages,
        max_tokens=500,
        stream=True,
        temperature=1.0,
        top_p=0.8
    )
    final_output = ""
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            final_output += chunk.choices[0].delta.content
    print(f"HIIIIII {final_output}")
    bool_array = return_array(category, final_output)
    return bool_array


def prompt_inference_local(category, user_prompt):
    bnb_config = {
        "load_in_4bit": True,
        "bnb_4bit_quant_type": "nf4",
        "bnb_4bit_compute_dtype": torch.float16,
        "bnb_4bit_use_double_quant": True,
    }
    model = AutoModelForCausalLM.from_pretrained(
        "microsoft/Phi-3.5-mini-instruct",
        device_map="cuda",
        torch_dtype="auto",
        trust_remote_code=True,
        quantization_config=bnb_config,
    )
    tokenizer = AutoTokenizer.from_pretrained("microsoft/Phi-3.5-mini-instruct")
    pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
    )
    generation_args = {
        "max_new_tokens": 500,
        "return_full_text": False,
        "temperature": 1.0,
        "top_p": 0.8,
        "do_sample": False,
    }

    with open("./prompts.txt", "r") as f:
        loaded_data = json.load(f)
    final_prompt = loaded_data[category] + f'\nSentence to Evaluate: "{user_prompt}"'
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": final_prompt},
    ]
    output = pipe(messages, **generation_args)
    return_text = output[0]["generated_text"]
    bool_array = return_array(category, return_text)
    return bool_array


def return_tbssa_outputs(input_text: str) -> list[list[bool]]:
    local = False

    def is_connected():
        try:
            socket.create_connection(("1.1.1.1", 53))
            print("Connected to Internet")
        except OSError:
            local = True
            print("Not Connected to Internet")

    is_connected()

    if local:
        prompt_llm = prompt_inference_local
    else:
        prompt_llm = prompt_llm_inference

    categories = ['depression', 'anxiety', 'adhd', 'schizophrenia', 'insomnia']

    final_lst = []
    for category in categories:
        arr = prompt_llm(category, input_text)
        final_lst.append(arr)

    return final_lst
