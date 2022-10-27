import pandas
from enum import Enum
from pydantic import BaseModel
from typing import Optional, Dict, List, Tuple, Any


class Column(str):
    def __init__(self, object: str):
        super().__init__()
        self.display = False
        self.display_name = self.__str__().replace('_', ' ').title()


class Filter(BaseModel):
    display_column: str
    filter_type: Optional[str] = None


class Checkboxes(Filter):
    source_column: str
    selected_values: Optional[Dict] = {}

    def __init__(self, **data):
        super().__init__(filter_type='Checkboxes', **data)


class Range(Filter):
    source_column: str
    selected_extrema: List[Any]

    def __init__(self, **data):
        super().__init__(filter_type='Range', **data)


class DoubleRange(Filter):
    source_columns: Tuple[str,str]
    selected_extrema: Optional[List[Any]] = []

    def __init__(self, **data):
        super().__init__(filter_type='DoubleRange', **data)


class FilterTable(BaseModel):
    base_dataframe: pandas.DataFrame
    current_view: Optional[pandas.DataFrame] = None
    filters: Optional[List[Any]] = []

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        super().__init__(**data)
        self.base_dataframe = self.base_dataframe.set_axis([Column(col_name) for col_name in self.base_dataframe.columns], axis='columns')
        if self.current_view is None:
            self.current_view = self.base_dataframe

