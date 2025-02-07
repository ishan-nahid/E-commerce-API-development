from typing import List
import models, schemas, auth
from datetime import timedelta
from auth import oauth2_scheme
from sqlalchemy.orm import Session
from database import engine, get_db
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import FastAPI, Depends, HTTPException, status

app = FastAPI()

models.Base.metadata.create_all(bind=engine)

##############  AUTHORIZATION START ################
@app.post("/register", response_model=schemas.User)
def register_user(user: schemas.UserCreate,
                  db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(email=user.email, name=user.name, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(),
                db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/logout")
async def logout(current_user: models.User = Depends(auth.get_current_user),
                 token: str = Depends(oauth2_scheme)):
    auth.blacklist_token(token)
    return {"message": "Successfully logged out"}

##############  AUTHORIZATION END ################

##############  CATEGORY START ################
@app.post("/categories", response_model=schemas.Category)
def create_category(category: schemas.CategoryCreate,
                    db: Session = Depends(get_db),
                    current_user: models.User = Depends(auth.get_current_user)):
    db_category = models.Category(**category.dict())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@app.get("/categories", response_model=List[schemas.Category])
def read_categories(db: Session = Depends(get_db),
                    current_user: models.User = Depends(auth.get_current_user)):
    return db.query(models.Category).all()

##############  CATEGORY END ################


##############  PRODUCT START ################
@app.post("/products", response_model=schemas.Product)
def create_product(product: schemas.ProductCreate,
                   db: Session = Depends(get_db),
                   current_user: models.User = Depends(auth.get_current_user)):
    db_product = models.Product(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

@app.get("/products", response_model=List[schemas.Product])
def read_products(skip: int = 0,
                  limit: int = 100,
                  db: Session = Depends(get_db)):
    products = db.query(models.Product).offset(skip).limit(limit).all()
    return products


##############  PRODUCT END ################


##############  CART START ################

@app.post("/cart/items", response_model=schemas.CartItem)
def add_to_cart(cart_item: schemas.CartItemBase,
                db: Session = Depends(get_db),
                current_user: models.User = Depends(auth.get_current_user)):
    product = db.query(models.Product).filter(models.Product.id == cart_item.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    cart = db.query(models.Cart).filter(models.Cart.user_id == current_user.id,
                                        models.Cart.is_open == True).first()
    
    if not cart:
        cart = models.Cart(user_id=current_user.id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    
    existing_item = db.query(models.CartItem).filter(models.CartItem.cart_id == cart.id,
                                                     models.CartItem.product_id == cart_item.product_id).first()
    
    if existing_item:
        existing_item.quantity += cart_item.quantity
        db_cart_item = existing_item
    else:
        db_cart_item = models.CartItem(cart_id=cart.id, product_id=cart_item.product_id, quantity=cart_item.quantity)
        db.add(db_cart_item)
    
    db.commit()
    db.refresh(db_cart_item)
    return db_cart_item


@app.get("/cart", response_model=schemas.CartResponse)
def view_cart(db: Session = Depends(get_db),
              current_user: models.User = Depends(auth.get_current_user)):
    cart = db.query(models.Cart).filter(
        models.Cart.user_id == current_user.id,
        models.Cart.is_open == True
    ).first()
    
    if not cart:
        return {
            "id": 0,
            "items": [],
            "total_price": 0.0
        }
    
    items_detail = []
    total_price = 0.0
    
    for item in cart.items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        item_total = product.price * item.quantity
        total_price += item_total
        items_detail.append({
            "item_id": item.id,
            "product_id": product.id,
            "product_name": product.name,
            "quantity": item.quantity,
            "price_per_unit": product.price,
            "item_total": item_total
        })
    
    return {
        "id": cart.id,
        "items": items_detail,
        "total_price": total_price
    }


##############  CART END ################


##############  ORDER START ################

@app.post("/orders/", response_model=schemas.Order)
def create_order(db: Session = Depends(get_db),
                 current_user: models.User = Depends(auth.get_current_user)):
    cart = db.query(models.Cart).filter(
        models.Cart.user_id == current_user.id,
        models.Cart.is_open == True
    ).first()
    
    if not cart or not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    total_amount = 0
    order_items = []

    for cart_item in cart.items:
        product = db.query(models.Product).filter(models.Product.id == cart_item.product_id).first()
        if product.stock < cart_item.quantity:
            raise HTTPException(status_code=400, detail=f"Not enough stock for product {product.name}")
        
        product.stock -= cart_item.quantity
        total_amount += product.price * cart_item.quantity
        
        order_items.append(models.OrderItem(
            product_id=cart_item.product_id,
            quantity=cart_item.quantity,
            price=product.price
        ))

    order = models.Order(
        user_id=current_user.id,
        total_amount=total_amount,
        items=order_items
    )

    db.add(order)
    cart.is_open = False  
    db.commit()
    db.refresh(order)
    return order

##############  ORDER END ################
