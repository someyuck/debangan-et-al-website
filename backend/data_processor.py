import random
import math
from typing import List, Dict
from transformers import pipeline
import utils
from polarity import get_polarity_handler
from extracted_concerns import extract_concerns_handler
from long_term import return_tbssa_outputs

unmask_category = pipeline("fill-mask", model="nlp4good/psych-search")

JSONFILE = "./scores.pkl"
DATE_SCORES_SIZES = [9, 7, 6, 7, 6]
MAX_SCORES = [27, 21, 18, 21, 18]
DATE_SCORES_LABELS = ["depression", "anxiety", "adhd", "schizophrenia", "insomnia"]
CONCERN_REANGES = [4, 4, 4, 4, 4]


def add_scores(a: List[int], b: List[int]):
    return [max(a[i], b[i]) for i in range(len(a))]  # hacky bitwise or


def get_cur_day_scores():
    def accumulate_scores(scores_list: List[utils.DateScores]) -> utils.DateScores:
        aggregate: utils.DateScores = scores_list[-1]
        print(f"lllll: {len(aggregate)}")

        for date_score in scores_list[:-1]:
            for key in aggregate[1]:
                aggregate[1][key] = add_scores(aggregate[1][key], date_score[1][key])

        return aggregate

    last_week: List[utils.DateScores] = utils.read_last_entries(JSONFILE, 7)
    return accumulate_scores(last_week)


def update_cur_day_scores(scores_to_add: utils.DateScores) -> utils.DateScores:
    # only call if current date is stored in file, else append
    cur_day_scores = get_cur_day_scores()

    for key in cur_day_scores[1]:
        cur_day_scores[1][key] = add_scores(
            cur_day_scores[1][key], scores_to_add[1][key]
        )

    utils.replace_last_entry(JSONFILE, cur_day_scores)
    return cur_day_scores


def calculate_phq_scores(
    week_scores: List[utils.DateScores], concern_ranges: List[int]
):
    print(week_scores)
    num_cols = {
        concern: len(week_scores[0][1][concern]) for concern in week_scores[0][1]
    }
    scores = {key: [0 for _ in range(num_cols[key])] for key in num_cols}

    for day in range(len(week_scores)):
        for concern in num_cols:
            for col in range(num_cols[concern]):
                scores[concern][col] += week_scores[day][1][concern][col]

    # changing score from list to int
    i = 0
    concern_score: Dict[str, int] = {key: 0 for key in num_cols}
    for concern in scores:
        for col in range(num_cols[concern]):
            concern_score[concern] += scores[concern][col] / 2
        concern_score[concern] = 100 * concern_score[concern] / MAX_SCORES[i]
        i += 1

    return concern_score


def get_cur_day_phq_scores(input_text: str):
    cur_date = utils.get_cur_date()
    lsts = return_tbssa_outputs(input_text)
    print(lsts)
    todays_scores: utils.DateScores = (
        cur_date,
        {cat: lst for cat, lst in zip(DATE_SCORES_LABELS, lsts)},
    )

    # update cur date in file
    if utils.is_cur_date_in_file(JSONFILE):
        update_cur_day_scores(todays_scores)
    else:
        utils.append_to_file(JSONFILE, [todays_scores])

    scores = calculate_phq_scores(utils.read_last_entries(JSONFILE, 7), CONCERN_REANGES)
    return list(scores.keys()), list(scores.values())


def get_cur_day_concern_labels(scores: list[int]):
    return [str(key) for key in scores]


def _predict_categories(input_text: str, num_cats: int) -> Dict[str, int]:
    categories = utils.get_categories()

    if len(input_text) < 1:
        return {}

    if not input_text[-1] == ".":
        input_text += "."

    prompt = f"{input_text} I should be diagnosed with [MASK]."
    results = unmask_category(prompt)
    filtered_results = [
        result for result in results if result["token_str"] in categories
    ]

    if len(filtered_results) < 1:
        return {}

    sorted_results = sorted(filtered_results, key=lambda x: x["score"], reverse=True)
    if len(sorted_results) > num_cats:
        sorted_results = sorted_results[:num_cats]

    TOTAL_PROB = sum([result["score"] for result in filtered_results])
    relative_probs = {
        res["token_str"]: (res["score"] / TOTAL_PROB) * 10 for res in filtered_results
    }

    print(relative_probs)

    return relative_probs


def process_data(input_text: str):
    polarity = get_polarity_handler(input_text)
    features = extract_concerns_handler(input_text)

    if polarity == "positive":
        intensities = [10]
        categories = ["positive outlook"]
    else:
        categories = _predict_categories(input_text, 3)
        intensities = list(categories.values())
        categories = list(categories.keys())
        print(intensities, categories)

    concernNames, cur_day_phq_scores = get_cur_day_phq_scores(input_text)
    cur_day_concern_labels = get_cur_day_concern_labels(cur_day_phq_scores)
    currentDate = utils.get_cur_date(change_itr=True)

    print(concernNames, cur_day_phq_scores, cur_day_concern_labels)

    return {
        "polarity": polarity,
        "features": features,
        "categories": categories,
        "intensity": intensities,
        "currentDate": currentDate,
        "categoryNames": concernNames,
        "categoryScores": cur_day_phq_scores,
        "categoryLabels": cur_day_concern_labels,
    }
