"""Auth + user profile — OWNER: Backend-2.

  POST /api/auth/register   create user (email, name, profile)
  POST /api/auth/login       issue session/JWT
  GET  /api/auth/me          current user + profile (feeds compute_targets)
Profile fields map 1:1 to schemas.UserProfile; store dietary prefs in
models.User.prefs_csv (see app.db.converters.parse_prefs).
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me")
def me():
    # TODO(Backend-2): return the authenticated user's profile
    return {"todo": "auth/me"}
