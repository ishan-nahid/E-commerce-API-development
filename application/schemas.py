from typing import List
from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class UserBase(BaseModel):
    email: str
    name: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    
    class Config:
        orm_mode = True

class CategoryBase(BaseModel):
    name: str

class CategoryCreate(CategoryBase):
    pass

class Category(CategoryBase):
    id: int
    
    class Config:
        orm_mode = True

class ProductBase(BaseModel):
    name: str
    description: str
    price: float
    stock: int
    category_id: int

class ProductFilter(BaseModel):
    category_id: Optional[int] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    in_stock: Optional[bool] = None

class ProductCreate(ProductBase):
    pass



class Product(ProductBase):
    id: int
    
    class Config:
        orm_mode = True


class CartItemBase(BaseModel):
    product_id: int
    quantity: int = 1

class CartResponse(BaseModel):
    id: int
    items: List[dict]  
    total_price: float
    
    class Config:
        from_attributes = True

class CartItem(CartItemBase):
    id: int
    
    class Config:
        orm_mode = True


class OrderItemBase(BaseModel):
    product_id: int
    quantity: int
    price: float

class OrderItem(OrderItemBase):
    id: int
    
    class Config:
        orm_mode = True

class OrderBase(BaseModel):
    total_amount: float

class Order(OrderBase):
    id: int
    created_at: datetime
    items: List[OrderItem]
    
    class Config:
        orm_mode = True