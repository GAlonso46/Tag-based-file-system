"""
Router de Autenticación
Endpoints: /register, /login, /me
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from .database import get_db
from .models import User
from .dependencies import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_active_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


# ==================== Schemas Pydantic ====================

class UserCreate(BaseModel):
    """Schema para crear usuario"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserResponse(BaseModel):
    """Schema de respuesta de usuario"""
    id: int
    username: str
    email: str
    is_admin: int
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    """Schema de token de acceso"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Datos dentro del token"""
    username: str | None = None


# ==================== Endpoints ====================

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """
    Registrar nuevo usuario
    
    - **username**: Nombre de usuario único (3-50 caracteres)
    - **email**: Email único y válido
    - **password**: Contraseña (mínimo 6 caracteres)
    
    Retorna el usuario creado (sin contraseña)
    """
    # Verificar si el username ya existe
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nombre de usuario ya está registrado"
        )
    
    # Verificar si el email ya existe
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )
    
    # Crear nuevo usuario
    hashed_password = get_password_hash(user.password)
    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login de usuario
    
    - **username**: Nombre de usuario
    - **password**: Contraseña
    
    Retorna un token JWT de acceso
    """
    # Buscar usuario
    user = db.query(User).filter(User.username == form_data.username).first()
    
    # Verificar usuario y contraseña
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Crear token de acceso
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


class LoginJSON(BaseModel):
    """Schema para login con JSON"""
    username: str
    password: str


@router.post("/login-json", response_model=Token)
def login_json(
    credentials: LoginJSON,
    db: Session = Depends(get_db)
):
    """
    Login de usuario con JSON (alternativa al form-data)
    
    - **username**: Nombre de usuario
    - **password**: Contraseña
    
    Retorna un token JWT de acceso
    """
    # Buscar usuario
    user = db.query(User).filter(User.username == credentials.username).first()
    
    # Verificar usuario y contraseña
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Crear token de acceso
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_active_user)):
    """
    Obtener información del usuario actual
    
    Requiere token JWT válido en el header:
    `Authorization: Bearer <token>`
    """
    return current_user


@router.post("/logout")
def logout():
    """
    Logout (placeholder)
    
    En JWT stateless, el logout se maneja en el cliente eliminando el token.
    Este endpoint existe por convención, pero no hace nada en el servidor.
    """
    return {"message": "Logout exitoso. Elimina el token del lado del cliente."}
