import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from database import create_document, get_documents, db
from schemas import Product

app = FastAPI(title="Food Shop API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProductResponse(Product):
    id: Optional[str] = None


@app.get("/")
def read_root():
    return {"message": "Food Shop Backend Running"}


@app.get("/api/products", response_model=List[ProductResponse])
def list_products(category: Optional[str] = None, search: Optional[str] = None, limit: int = Query(100, ge=1, le=200)):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    filter_dict = {}
    if category:
        filter_dict["category"] = category

    # Simple search across title/description using case-insensitive regex
    if search:
        filter_dict["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]

    docs = get_documents("product", filter_dict, limit)

    # Normalize response and convert _id to string id
    results = []
    for d in docs:
        d = {**d}
        d["id"] = str(d.pop("_id", ""))
        # Remove timestamps if present but not serializable
        if "created_at" in d:
            d["created_at"] = str(d["created_at"])  # for completeness
        if "updated_at" in d:
            d["updated_at"] = str(d["updated_at"])  # for completeness
        results.append(d)

    return results


@app.post("/api/products", status_code=201)
def create_product(product: Product):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        inserted_id = create_document("product", product)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/categories", response_model=List[str])
def list_categories():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        categories = db["product"].distinct("category")
        return sorted([c for c in categories if c])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/seed")
def seed_products():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    sample_products = [
        Product(title="Margherita Pizza", description="Classic pizza with tomato, mozzarella, and basil", price=9.99, category="Pizza", in_stock=True),
        Product(title="Pepperoni Pizza", description="Pepperoni, mozzarella, tomato sauce", price=11.49, category="Pizza", in_stock=True),
        Product(title="Veggie Burger", description="Plant-based patty with fresh veggies", price=8.99, category="Burgers", in_stock=True),
        Product(title="Cheeseburger", description="Beef patty, cheese, lettuce, tomato", price=10.49, category="Burgers", in_stock=True),
        Product(title="Chicken Caesar Salad", description="Grilled chicken with romaine and Caesar dressing", price=7.99, category="Salads", in_stock=True),
        Product(title="Sushi Platter", description="Assorted rolls and nigiri", price=14.99, category="Sushi", in_stock=True),
        Product(title="Pad Thai", description="Stir-fried rice noodles with tamarind sauce", price=12.49, category="Asian", in_stock=True),
        Product(title="Chocolate Cake", description="Rich and moist chocolate cake slice", price=4.99, category="Desserts", in_stock=True),
    ]

    try:
        if db["product"].count_documents({}) == 0:
            for p in sample_products:
                create_document("product", p)
            inserted = len(sample_products)
        else:
            inserted = 0
        return {"inserted": inserted, "total": db["product"].count_documents({})}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
