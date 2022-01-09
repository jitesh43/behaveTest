import logging
import os
import glob
import json
from allure_commons.utils import md5
from pathlib import Path
from behave.__main__ import run_behave
from behave.configuration import Configuration
from behave.tag_expression import TagExpression
from dotenv import load_dotenv

from backend.utils.utils import is_truthy

PROJECT_ROOT = Path(__file__).resolve().parent


log = logging.getLogger(__name__)


def get_env(name, required=True):
    value = os.getenv(name)
    if required:
        assert value, f"No {name} environment variable found. Bailing out."
    return value


def update_allure_result_json_files(
    reports_folder_path, hardware, user_location
):
    """Update allure '*result.json' files.

    :param reports_folder_path: path of all json file's reports folder
    :type reports_folder_path: Path
    :param hardware: name of the hardware
    :type hardware: str
    :param user_location: user location
    :type user_location: str
    """
    json_files_path = glob.glob(str(reports_folder_path) + "/*result.json")
    for path in json_files_path:
        with open(path, "r") as json_file:
            json_data = json.load(json_file)

        append_string = f" -- {hardware} -- {user_location}".lower()
        json_data["name"] += append_string
        json_data["historyId"] = md5(json_data["name"])

        with open(path, "w") as new_json_file:
            json.dump(json_data, new_json_file)


def main():
    tags = TagExpression(get_env("TAGS").split())
    log.info(f"Using these tags: {tags}")
    tags_option = " ".join([f"--tags={','.join(tag)}" for tag in tags.ands])
    reports = get_env("REPORTS")
    reports = PROJECT_ROOT / reports
    verbose = is_truthy(get_env("VERBOSE", required=False))
    feature_order = " ".join(
        feature_path.strip()
        for feature_path in get_env("FEATURE_ORDER").split(",")
        if Path(PROJECT_ROOT / feature_path.strip()).exists()
    )
    arguments = (
        f"{feature_order} -f allure_behave.formatter:AllureFormatter "
        f"-o {reports} --no-skipped -f plain {tags_option}"
    )
    configuration = Configuration(arguments, verbose=verbose)
    run_behave(configuration)

    # adding hardware and user location to scenario headlines in allure report
    hardware = get_env("HARDWARE")
    user_location = (
        "Localhost" if is_truthy(get_env("IS_LOCALHOST")) else "Remotehost"
    )
    update_allure_result_json_files(reports, hardware, user_location)


if __name__ == "__main__":
    env_path = Path(".") / ".env"
    env = load_dotenv(dotenv_path=env_path)
    main()
