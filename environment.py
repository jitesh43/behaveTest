"""The environment.py module may define code to run before and after certain
events during your testing."""
import json
import logging
import os
from pathlib import Path
import requests
import ruamel.yaml as yaml
from allure import attach
from allure_commons.types import AttachmentType
from behave import fixture, use_fixture, use_step_matcher
from behave.model_core import Status
from requests.status_codes import codes
from selenium import webdriver
from selenium.webdriver import DesiredCapabilities
from features.teardown import teardown

PROJECT_ROOT = Path(__file__).resolve().parent
FEATURE_DEFAULT_DOWNLOAD = "/tmp"
use_step_matcher("re")  # why are we not using parse or cfparse?
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


@fixture
def browser_chrome(context):
    """Get chrome browser either from docker domain or locally."""
    environment = os.getenv("ENVIRONMENT")
    context.host = os.getenv("SELENIUM_TARGET_HOST")
    context.port = os.getenv("SELENIUM_TARGET_PORT")
    # Set of desired capabilities
    capabilities = DesiredCapabilities.CHROME.copy()
    capabilities["goog:loggingPrefs"] = {
        "browser": "ALL",
        "performance": "ALL",
    }
    options = webdriver.ChromeOptions()
    options.add_experimental_option(
        "prefs", {"download.default_directory": f"{FEATURE_DEFAULT_DOWNLOAD}"}
    )
    capabilities.update(options.to_capabilities())
    if environment and environment == "docker":
        driver = get_remote_driver(capabilities)
        log.debug("Got remote Chrome driver.")
    else:
        log.info("Creating local Chrome instance.")
        driver = webdriver.Chrome(desired_capabilities=capabilities)
        log.debug("Got local Chrome driver.")

    yield driver
    driver.quit()


@fixture
def configuration(context):
    """Get the configuration from the test box and put in the context."""
    port = f":{context.port}" if context.port != "80" else ""
    yield


@fixture
def load_selectors(context, path: Path):
    """Get the selectors and place them in the root context."""
    context.selectors = yaml.load(path.read_text(), Loader=yaml.Loader)
    log.info(f"Loaded {len(context.selectors)} selectors.")
    yield
    context.selectors = None


def before_all(context):
    """Load the driver into the context and get the configuration.

    :param context: behave.runner.Context
    """
    try:
        log.info("Running before all: getting driver and the configuration...")
        if os.getenv("SELENIUM_DRIVER_NAME") == "firefoxnode":
            driver = use_fixture(browser_firefox, context)
        else:
            driver = use_fixture(browser_chrome, context)
        context.driver = driver
        context.drivers = {"default": driver}
        use_fixture(configuration, context)
        selector_file = PROJECT_ROOT / "config" / "selectors.yaml"
        use_fixture(load_selectors, context, selector_file)
        log.info("Driver is ready and configuration is found.")
    except Exception as e:
        log.exception(e)
        raise e


def after_scenario(context, scenario):
    """Attach a screenshot and browser console logs if scenario is failed.

    :param context: behave.runner.Context
    :param scenario: behave scenario
    """
    # Scenario context variable
    context_variable_dict = {
        key: str(value) for key, value in context.vars.items()
    }
    context_logs = json.dumps(context_variable_dict)
    attach(
        context_logs,
        name="Context variable",
        attachment_type=AttachmentType.JSON,
    )

    if scenario.status == Status.failed:
        # Screenshot
        attach(
            context.driver.get_screenshot_as_png(),
            name=scenario.name,
            attachment_type=AttachmentType.PNG,
        )

        # Browser Console Log
        browser_logs = json.dumps(context.driver.get_log("browser"), indent=4)
        attach(
            browser_logs,
            name="Browser Console Log",
            attachment_type=AttachmentType.JSON,
        )

        # Network & Page domain events logs.
        if os.getenv("BROWSER_NETWORK_LOGS") == "true":
            performance_logs = json.dumps(
                context.driver.get_log("performance"), indent=4
            )
            attach(
                performance_logs,
                name="Network & Page domain events logs",
                attachment_type=AttachmentType.JSON,
            )
     teardown(context)


def before_scenario(context, scenario):
    """Before every scenario go to the root url.

    :param context: behave.runner.Context
    :param scenario: behave scenario
    """
    # Clear cookies : expiration-time, sessionid and csrftoken
    context.driver.delete_all_cookies()
    root_url = f"http://{context.host}:{context.port}"
    context.driver.get(root_url)
    log.debug(f"Connected to the root url: {root_url}.")

    # Reset Scenario context data dict
    context.vars = {}
    context.created_users = []

    # Verify services are up and running before running each scenario


def before_feature(context, feature):
    """Before every feature.

    :param context: behave.runner.Context
    """
    # todo: needs to go!
    context.feature_vars = {}
