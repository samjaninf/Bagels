import warnings
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from bagels.locations import config_file


class Defaults(BaseModel):
    period: Literal["day", "week", "month", "year"] = "week"
    first_day_of_week: int = Field(ge=0, le=6, default=6)
    date_format: str = "%d/%m"
    round_decimals: int = 2
    plot_marker: Literal["braille", "fhd", "hd", "dot"] = "braille"


class DatemodeHotkeys(BaseModel):
    go_to_day: str = "g"


class HomeHotkeys(BaseModel):
    cycle_tabs: str = "c"
    budgets: str = "b"
    new_transfer: str = "t"
    toggle_splits: str = "s"
    display_by_date: str = "q"
    display_by_person: str = "w"
    advance_filter: str = "f"
    cycle_offset_type: str = "."
    toggle_income_mode: str = "/"
    select_prev_account: str = "["
    select_next_account: str = "]"
    toggle_use_account: str = "\\"
    datemode: DatemodeHotkeys = DatemodeHotkeys()


class RecordModalHotkeys(BaseModel):
    new_split: str = "ctrl+a"
    new_paid_split: str = "ctrl+s"
    delete_last_split: str = "ctrl+d"


class CategoriesHotkeys(BaseModel):
    new_subcategory: str = "s"
    browse_defaults: str = "b"


class Hotkeys(BaseModel):
    new: str = "a"
    delete: str = "d"
    edit: str = "e"
    toggle_jump_mode: str = "v"
    home: HomeHotkeys = HomeHotkeys()
    record_modal: RecordModalHotkeys = RecordModalHotkeys()
    categories: CategoriesHotkeys = CategoriesHotkeys()


class Symbols(BaseModel):
    line_char: str = "│"
    finish_line_char: str = "╰"
    split_paid: str = "✓"
    split_unpaid: str = "⨯"
    category_color: str = "●"
    amount_positive: str = "+"
    amount_negative: str = "-"


class BudgetingStates(BaseModel):
    # ---------- Income policies --------- #
    income_assess_metric: Literal["periodIncome", "fallback"] = (
        "periodIncome"  # use the current period's income, or if less than threshold, use the past period's income
    )
    income_assess_threshold: float = (
        100  # if income less than this, we assume has no income
    )
    income_assess_fallback: float = (
        3500  # if income less than threshold, we use this as the income
    )
    # -------- Savings budgetting -------- #
    savings_assess_metric: Literal["percentagePeriodIncome", "setAmount"] = (
        "percentagePeriodIncome"
    )
    savings_percentage: float = (
        0.2  # used only if savings_assess_metric is percentagePeriodIncome
    )
    savings_amount: float = 0  # used only if savings_assess_metric is setAmount
    # ---------- MNW budgetting ---------- #
    wants_spending_assess_metric: Literal["percentageQuota", "setAmount"] = (
        "percentageQuota"  # percentage of all expenses
    )
    wants_spending_percentage: float = (
        0.2  # used only if wants_spending_assess_metric is setPercentage
    )
    wants_spending_amount: float = (
        0  # used only if wants_spending_assess_metric is setAmount
    )


class State(BaseModel):
    theme: str = "dark"
    check_for_updates: bool = True
    footer_visibility: bool = True
    budgeting: BudgetingStates = BudgetingStates()


class Config(BaseModel):
    hotkeys: Hotkeys = Hotkeys()
    symbols: Symbols = Symbols()
    defaults: Defaults = Defaults()
    state: State = State()

    def __init__(self, **data):
        config_data = self._load_yaml_config()
        merged_data = {**self.model_dump(), **config_data, **data}
        super().__init__(**merged_data)
        self.ensure_yaml_fields()

    def _load_yaml_config(self) -> dict[str, Any]:
        config_path = config_file()
        if not config_path.is_file():
            return {}

        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
                return config if isinstance(config, dict) else {}
        except Exception as e:
            warnings.warn(f"Error loading config file: {e}")
            return {}

    def ensure_yaml_fields(self):
        try:
            with open(config_file(), "r") as f:
                config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            config = {}

        def update_config(default, current):
            for key, value in default.items():
                if isinstance(value, dict):
                    current[key] = update_config(value, current.get(key, {}))
                elif key not in current:
                    current[key] = value
            return current

        default_config = self.model_dump()
        config = update_config(default_config, config)

        with open(config_file(), "w") as f:
            yaml.dump(config, f, default_flow_style=False)

    @classmethod
    def get_default(cls):
        return cls(
            hotkeys=Hotkeys(), symbols=Symbols(), defaults=Defaults(), state=State()
        )


CONFIG = None


def load_config():
    f = config_file()
    if not f.exists():
        try:
            f.touch()
            with open(f, "w") as f:
                yaml.dump(Config.get_default().model_dump(), f)
        except OSError:
            pass

    global CONFIG
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        CONFIG = Config()  # ignore warnings about empty env file


def write_state(key: str, value: Any) -> None:
    """Write a state value to the config.yaml file, supporting nested keys with dot operator."""
    try:
        with open(config_file(), "r") as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        config = {}

    keys = key.split(".")
    d = config.setdefault("state", {})
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value

    with open(config_file(), "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    # update the global config object
    global CONFIG
    d = CONFIG.state
    for k in keys[:-1]:
        d = getattr(d, k)
    setattr(d, keys[-1], value)
