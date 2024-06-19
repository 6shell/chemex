from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordRequestForm

from ..dependencies import get_current_user, databaseSession
from ..services import auth
from ..services.auth import authenticate, create_access_token
from ..services.user import get_scopes
from ..database import schemas, crud, tables
from ..utils import crypt

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    dependencies=[],
    responses={404: {"description": "Not found"}},
)


@router.get("/init")
async def init(
        db: databaseSession,
):
    admin = crud.select_username(db, tables.User, "admin")
    if admin:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cela has been inited.",
        )
    username = "admin"
    email = "admin@localhost"
    name = "Admin"
    password = "admin"
    auth.create_super_admin(
        db,
        schemas.UserCreateForm(
            username=username,
            email=email,
            name=name,
            password=password,
            creator_id=0
        )
    )
    raise HTTPException(
        status_code=status.HTTP_200_OK,
        detail="Cela inited successfully, please login with username 'admin' and password 'admin'.",
    )


@router.post("/login")
async def login(
        db: databaseSession,
        form_data: OAuth2PasswordRequestForm = Depends(),
):
    user = authenticate(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scopes = get_scopes(db, user.id)
    access_token = create_access_token(data={"user_id": user.id, "scopes": scopes})
    return {"access_token": access_token, "type": "bearer"}


@router.get("/me")
async def me(
        current_user: schemas.User = Security(get_current_user, scopes=["auth:me"]),
):
    return current_user


@router.put("/me")
async def update_me(
        db: databaseSession,
        form_data: list[schemas.UpdateForm],
        current_user: schemas.User = Security(get_current_user, scopes=["auth:me"]),
):
    current_user = crud.update(db, tables.User, current_user.id, form_data)
    return current_user


@router.put("/change_password")
async def change_password(
        db: databaseSession,
        form_data: schemas.UserChangePasswordForm,
        current_user: schemas.User = Security(get_current_user, scopes=["auth:me"]),
):
    user = authenticate(db, current_user.username, form_data.old_password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    update_form = [
        schemas.UpdateForm(key="hashed_password", value=crypt.hash_password(form_data.new_password))
    ]
    current_user = crud.update(db, tables.User, current_user.id, update_form)
    return current_user


@router.post("/renew")
async def refresh_scopes(
        db: databaseSession,
        current_user: schemas.User = Security(get_current_user, scopes=["auth:me"]),
):
    scopes = get_scopes(db, current_user.id)
    access_token = create_access_token(data={"user_id": current_user.id, "scopes": scopes})
    return {"access_token": access_token, "type": "bearer"}
