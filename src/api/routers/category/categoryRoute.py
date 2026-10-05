from fastapi import APIRouter, Depends
from sqlmodel import delete, exists, select
from src.api.routers.category.fn import (
    build_category_tree,
    calculate_category_level,
)
from src.api.models.product_model.productModel import Product
from src.api.core.operation.media import uploadMediaFiles
from src.api.core.utility import uniqueSlugify
from src.api.core.operation import listRecords, serialize_obj
from src.api.core.response import api_response, raiseExceptions
from src.api.core.dependencies import (
    GetSession,
    ListQueryParams,
    requirePermission,
    requirePermission,
)
from src.api.models.category_model import (
    Category,
    CategoryForm,
    CategoryRead,
    CategoryTreeRead,
)

router = APIRouter(prefix="/category", tags=["Category"])


@router.post("/create")
async def create(
    session: GetSession,
    request: CategoryForm = Depends(),
    user=requirePermission("category:create"),
):
    """Create a new category with auto-level and root assignment."""
    # 1️⃣ Calculate hierarchical level

    level = calculate_category_level(session, request.parent_id)
    # 2️⃣ Initialize model
    data = serialize_obj(request)
    await uploadMediaFiles(session, data, request)
    data = Category(**data, level=level)

    # 3️⃣ Generate unique slug
    data.slug = uniqueSlugify(session, Category, data.name)

    # add to session
    session.add(data)
    session.flush()  # assigns 'id' without committing

    # 4️⃣ Determine root_id
    if data.parent_id is None or data.parent_id == 0:
        data.root_id = data.id  # top-level category
    else:
        parent = session.get(Category, data.parent_id)
        data.root_id = parent.root_id if parent.root_id else parent.id

        # Top-level root fix
    if data.root_id is None:
        data.root_id = data.id

    session.commit()  # commit everything in one transaction
    session.refresh(data)

    return api_response(
        200, "Category Created Successfully", CategoryRead.model_validate(data)
    )


@router.put("/update/{id}")
def update_category(
    id: int,
    session: GetSession,
    request: CategoryForm = Depends(),
    user=requirePermission("category:update"),
):
    """Update category safely, preserving tree structure."""

    category = session.get(Category, id)
    raiseExceptions((category, 404, "Category not found"))

    # ==========================
    # Handle Parent Change
    # ==========================
    if request.parent_id is not None and request.parent_id != category.parent_id:

        if request.parent_id == 0:
            category.parent_id = None
            category.level = 1
            category.root_id = None  # or category.id after commit

        else:
            # ❌ Cannot be its own parent
            if request.parent_id == id:
                return api_response(400, "A category cannot be its own parent")

            parent = session.get(Category, request.parent_id)
            if not parent:
                return api_response(400, "Parent category not found")

            # ❌ Prevent level overflow
            if parent.level >= 3:
                return api_response(400, "Cannot move under a level 3 category")

            # ❌ Prevent circular reference
            def is_descendant(child_id, parent_id):
                while child_id:
                    node = session.get(Category, child_id)
                    if not node:
                        break
                    if node.parent_id == parent_id:
                        return True
                    child_id = node.parent_id
                return False

            if is_descendant(request.parent_id, id):
                return api_response(400, "Cannot move category inside its own subtree")

            # ✅ Apply hierarchy update
            category.parent_id = request.parent_id
            category.level = parent.level + 1
            category.root_id = parent.root_id if parent.root_id else parent.id

    # ==========================
    # Update Fields (safe)
    # ==========================
    if request.name:
        category.name = request.name
        category.slug = uniqueSlugify(session, Category, request.name)

    if request.details is not None:
        category.details = request.details

    if request.icon is not None:
        category.icon = request.icon

    if request.image is not None:
        category.image = request.image  # handle upload separately if needed

    if request.admin_commission_rate is not None:
        category.admin_commission_rate = request.admin_commission_rate

    if request.is_active is not None:
        category.is_active = request.is_active

    # ==========================
    # Save
    # ==========================
    session.add(category)
    session.commit()
    session.refresh(category)

    return api_response(
        200,
        "Category updated successfully",
        CategoryRead.model_validate(category),
    )


@router.delete("/delete/{id}")
def delete_category(
    id: int,
    session: GetSession,
    user=requirePermission("category:delete"),
):
    """Delete category safely (prevent delete if it has children)."""

    category = session.get(Category, id)
    raiseExceptions((category, 404, "Category not found"))

    # ==========================
    # Check children
    # ==========================
    has_children = session.exec(
        select(Category).where(Category.parent_id == id)
    ).first()

    if has_children:
        return api_response(
            400,
            "Cannot delete category with child categories. Remove or move them first.",
        )

    # ==========================
    # Optional: Check products
    # ==========================
    has_products = session.exec(select(exists().where(Product.category_id == id))).one()

    if has_products:
        return api_response(400, "Cannot delete category with assigned products")

    # ==========================
    # Delete
    # ==========================
    session.delete(category)
    session.commit()

    return api_response(200, "Category deleted successfully")


@router.delete("/delete-parent/{id}")
def deleteMany(
    id: int,
    session: GetSession,
    user=requirePermission("system:*"),
):
    category = session.get(Category, id)
    raiseExceptions((category, 404, "category not found"))

    # ==========================
    # Get all category IDs in tree
    # ==========================
    category_ids = session.exec(
        select(Category.id).where((Category.id == id) | (Category.root_id == id))
    ).all()

    # ==========================
    # Check products
    # ==========================
    has_products = session.exec(
        select(exists().where(Product.category_id.in_(category_ids)))
    ).one()

    if has_products:
        return api_response(400, "Cannot delete: categories in this tree have products")

    # ==========================
    # Delete in ONE query
    # ==========================
    session.exec(delete(Category).where(Category.id.in_(category_ids)))
    session.commit()

    return api_response(200, f"Category tree '{category.name}' deleted successfully")


@router.get(
    "/read/{id_slug}",
    description="Category ID (int) or slug (str)",
    response_model=CategoryTreeRead,
)
def get(id_slug: str, session: GetSession):
    # Check if it's an integer ID
    if id_slug.isdigit():
        read = session.get(Category, int(id_slug))
        print("Finding by ID:", read)
    else:
        # Otherwise treat as slug
        read = (
            session.exec(select(Category).where(Category.slug.ilike(id_slug)))
            .scalars()
            .first()
        )
    raiseExceptions((read, 404, "Category not found"))

    return api_response(200, "Category Found", CategoryTreeRead.model_validate(read))


@router.get("/list", response_model=list[CategoryTreeRead])
def list(query_params: ListQueryParams):
    query_params = vars(query_params)

    searchFields = ["name", "slug", "details"]

    result = listRecords(
        query_params=query_params,
        searchFields=searchFields,
        Model=Category,
    )

    # Convert DB objects → Pydantic
    list_data = [CategoryRead.model_validate(item) for item in result["data"]]

    # Build tree
    tree = build_category_tree(list_data)

    return api_response(200, "Categories Found", tree, result["total"])
