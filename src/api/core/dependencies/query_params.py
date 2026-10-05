from fastapi import Query, Depends
from typing import Annotated, Optional


# use double commas otherwise it will not work
class list_query_params:
    def __init__(
        self,
        dateRange: Optional[str] = Query(
            None, description="Example : ['created_at', '01-01-2025', '01-12-2025']"
        ),
        numberRange: Optional[str] = Query(
            None, description="Example : ['amount', 0, 100000]"
        ),
        searchTerm: str | None = Query(None, description="Search term"),
        columnFilters: Optional[str] = Query(
            None, description='Example : [["name","car"],["description","product"]]'
        ),
        stringArrayFilters: Optional[str] = Query(
            None, description="Example: [['tags',['tag1','tag2']]]"
        ),
        objectArrayFilters: Optional[str] = Query(
            None,
            description='Example: [[ "attributes", ["name","color"], ["values", ["value","Red"]]]]',
        ),
        deepFilters: Optional[str] = Query(
            None,
            description='Format: [["field.path", value or [values]]],Supports string (exact/like), boolean, number, JSON array (permissions), and deep relations. Example: [["user_roles.role.name","admin"],["users.is_active",true],["user_roles.role.permissions",["all","user-create"]]]',
        ),
        page: int = Query(1, description="Page number"),
        skip: int = Query(0, description="Number of items to skip"),
        limit: int = Query(10, description="Number of items to return"),
        sort: Optional[str] = Query(
            None, description="Example : ['created_at|price','asc|desc']"
        ),
    ):
        self.dateRange = dateRange
        self.skip = skip
        self.limit = limit
        self.searchTerm = searchTerm
        self.columnFilters = columnFilters
        self.stringArrayFilters = stringArrayFilters
        self.objectArrayFilters = objectArrayFilters
        self.deepFilters = deepFilters
        self.page = page
        self.numberRange = numberRange
        self.sort = sort
