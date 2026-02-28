from dataclasses import dataclass
from fastapi import Request, HTTPException, status

@dataclass
class UserCtx:
    username: str
    roles: set[str]

def get_user(request: Request) -> UserCtx:
    # oauth2-proxy sets X-Auth-Request-Preferred-Username and X-Auth-Request-Groups
    username = request.headers.get("X-Auth-Request-Preferred-Username") or request.headers.get("X-Auth-Request-User") or "unknown"
    groups = request.headers.get("X-Auth-Request-Groups", "")
    roles = set([g.strip() for g in groups.split(",") if g.strip()])
    return UserCtx(username=username, roles=roles)

def require_role(user: UserCtx, *allowed: str):
    if not (user.roles.intersection(set(allowed))):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
