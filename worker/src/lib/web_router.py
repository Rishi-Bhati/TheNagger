"""
lib/web_router.py — Routes dashboard API requests & HTMX partials.
Includes strict authentication and authorization checks to prevent IDOR and BAC.
"""
import json
import logging
from datetime import datetime
from workers import Response

from .telegram_auth import verify_telegram_login, create_session_token, verify_session_token
from .supabase_client import SupabaseDB
from .html_renderer import render_task_list, render_add_task_form, render_settings_form
from .utils import parse_datetime, parse_frequency

logger = logging.getLogger(__name__)

# Must match frontend origin
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "https://nagger-dashboard.pages.dev",  # Update to actual pages dev domain if needed
    "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, Cookie",
    "Access-Control-Allow-Credentials": "true",
}

def _cors_response(body, status=200, headers=None):
    h = dict(CORS_HEADERS)
    if headers:
        h.update(headers)
    return Response(body, status=status, headers=h)

def _get_cookie(request, name: str) -> str:
    cookie_header = request.headers.get("Cookie") or request.headers.get("cookie")
    if not cookie_header:
        return None
    
    cookies = cookie_header.split(";")
    for cookie in cookies:
        cookie = cookie.strip()
        if cookie.startswith(f"{name}="):
            return cookie[len(name)+1:]
    return None

async def verify_session(request, env) -> int:
    """Verifies the secure session cookie. Returns user_id or None."""
    token = _get_cookie(request, "nagger_session")
    if not token:
        return None
    return verify_session_token(token, getattr(env, "SESSION_SECRET", ""))

async def handle_telegram_auth(request, env):
    """
    Validates Telegram Login Widget data, registers user if needed,
    and returns a secure HttpOnly session cookie.
    """
    url = request.url
    qs = url.split("?")[1] if "?" in url else ""
    params = {}
    for pair in qs.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k] = v
            
    user_data = verify_telegram_login(params, getattr(env, "TELEGRAM_TOKEN", ""))
    if not user_data:
        return _cors_response('{"error": "Invalid Telegram authentication"}', status=401)
        
    user_id = user_data["telegram_id"]
    
    # Upsert user record in Supabase securely (Server-side)
    db = SupabaseDB(env.SUPABASE_URL, env.SUPABASE_KEY)
    try:
        await db.update_user_activity(user_id, user_data.get("username"), f"{user_data.get('first_name','')} {user_data.get('last_name','')}".strip())
    except Exception as e:
        logger.error(f"Failed to upsert user during auth: {e}")
        
    # Generate secure session token
    token = create_session_token(user_id, getattr(env, "SESSION_SECRET", ""))
    
    # Set secure HttpOnly cookie
    headers = {
        "Set-Cookie": f"nagger_session={token}; HttpOnly; Secure; SameSite=None; Path=/; Max-Age=604800",
        "Content-Type": "application/json"
    }
    
    return _cors_response('{"status": "ok"}', status=200, headers=headers)

async def route_api(request, path, env):
    """Main dashboard API router."""
    if request.method == "OPTIONS":
        return _cors_response("", status=204)
        
    if path == "/api/auth/telegram":
        return await handle_telegram_auth(request, env)
        
    # All routes below require authentication
    user_id = await verify_session(request, env)
    if not user_id:
        return _cors_response('{"error": "Unauthorized"}', status=401)
        
    db = SupabaseDB(env.SUPABASE_URL, env.SUPABASE_KEY)
    
    try:
        # ---- HTMX PARTIALS ----
        if path.startswith("/api/partials/"):
            return await render_partial(path, user_id, request, db)
            
        # ---- JSON/REST ENDPOINTS ----
        if path == "/api/tasks":
            if request.method == "POST":
                return await create_task(user_id, request, db)
                
        if path.startswith("/api/tasks/"):
            parts = path.split("/")
            if len(parts) >= 4:
                try:
                    user_task_id = int(parts[3])
                except ValueError:
                    return _cors_response("Invalid task ID", status=400)
                    
                if path.endswith("/done") and request.method == "POST":
                    return await mark_done(user_id, user_task_id, db)
                    
                if request.method == "DELETE":
                    return await delete_task(user_id, user_task_id, db)
                    
        if path == "/api/settings":
            if request.method == "PATCH":
                return await update_settings(user_id, request, db)
                
        return _cors_response("Not found", status=404)
    except Exception as e:
        logger.error(f"API Error: {e}")
        return _cors_response(f"Internal Server Error", status=500)

async def render_partial(path: str, user_id: int, request, db: SupabaseDB):
    """Renders server-side HTML for HTMX."""
    if path == "/api/partials/task-list":
        url = request.url
        qs = url.split("?")[1] if "?" in url else ""
        filter_type = "active"
        for pair in qs.split("&"):
            if pair.startswith("filter="):
                filter_type = pair.split("=")[1]
                
        include_completed = (filter_type == "completed")
        tasks = await db.get_user_tasks(user_id, include_completed=include_completed)
        
        # Filter for overdue or active
        now = datetime.utcnow()
        filtered = []
        for t in tasks:
            if filter_type == "completed" and t.get("completed"):
                filtered.append(t)
            elif filter_type == "active" and not t.get("completed"):
                dl = t.get("deadline")
                if not dl or (isinstance(dl, datetime) and dl > now):
                    filtered.append(t)
            elif filter_type == "overdue" and not t.get("completed"):
                dl = t.get("deadline")
                if dl and isinstance(dl, datetime) and dl <= now:
                    filtered.append(t)
                    
        tz_str = await db.get_user_timezone(user_id)
        html = render_task_list(filtered, tz_str, empty_msg=f"No {filter_type} tasks.")
        return _cors_response(html, headers={"Content-Type": "text/html"})
        
    elif path == "/api/partials/task-form":
        html = render_add_task_form()
        return _cors_response(html, headers={"Content-Type": "text/html"})
        
    elif path == "/api/partials/settings":
        # Get settings from users table
        rows = await db._get("users", {"user_id": f"eq.{user_id}"})
        user_data = rows[0] if rows else {}
        html = render_settings_form(
            timezone=user_data.get("timezone", "UTC"),
            start=user_data.get("active_hours_start", "08:00"),
            end=user_data.get("active_hours_end", "22:00"),
            threshold=user_data.get("escalation_threshold", 60)
        )
        return _cors_response(html, headers={"Content-Type": "text/html"})
        
    return _cors_response("Partial not found", status=404)

async def create_task(user_id: int, request, db: SupabaseDB):
    """Securely creates a task for the authenticated user."""
    # HTMX sends form data, need to parse appropriately, or JSON if fetch
    # Using request.formData() equivalent in Python Workers?
    # For now, let's assume it's form data
    try:
        # Pyodide worker `request.formData()` is async
        form = await request.formData()
        title = form.get("title")
        description = form.get("description", "")
        deadline_str = form.get("deadline")
        freq_str = form.get("frequency", "30m")
    except Exception:
        return _cors_response("Invalid form data", status=400)
        
    if not title or not deadline_str:
        return _cors_response("Title and deadline required", status=400)
        
    tz = await db.get_user_timezone(user_id)
    deadline = parse_datetime(deadline_str, tz)
    if not deadline:
        return _cors_response("Invalid deadline", status=400)
        
    freq = parse_frequency(freq_str)
    if not freq:
        return _cors_response("Invalid frequency", status=400)
        
    # Get user settings
    rows = await db._get("users", {"user_id": f"eq.{user_id}"})
    u = rows[0] if rows else {}
    start = u.get("active_hours_start", "08:00")
    end = u.get("active_hours_end", "22:00")
    escalation = u.get("escalation_threshold", 60)
        
    freq_type, freq_value = freq
    user_task_id = await db.add_task(user_id, title, description, deadline)
    actual_id = await db.get_actual_task_id(user_id, user_task_id)
    
    await db.add_reminder(
        actual_id, freq_type, freq_value,
        start_time=start, end_time=end,
        escalation_enabled=True, escalation_threshold=escalation,
    )
    
    # Return the new task list (HTMX swap target is #task-feed)
    # Re-render active tasks
    tasks = await db.get_user_tasks(user_id, include_completed=False)
    now = datetime.utcnow()
    active = [t for t in tasks if not t.get("deadline") or t.get("deadline") > now]
    html = render_task_list(active, tz, empty_msg="No active tasks.")
    return _cors_response(html, headers={"Content-Type": "text/html"})

async def mark_done(user_id: int, user_task_id: int, db: SupabaseDB):
    """Securely marks a task as done, verifying ownership."""
    actual_id = await db.get_actual_task_id(user_id, user_task_id)
    if not actual_id:
        return _cors_response("Task not found or unauthorized", status=403)
        
    await db.update_task(actual_id, completed=True, completed_at=datetime.utcnow())
    return _cors_response("", status=200) # HTMX outerHTML swap removes the card

async def delete_task(user_id: int, user_task_id: int, db: SupabaseDB):
    """Securely deletes a task, verifying ownership."""
    actual_id = await db.get_actual_task_id(user_id, user_task_id)
    if not actual_id:
        return _cors_response("Task not found or unauthorized", status=403)
        
    await db.delete_task(actual_id)
    return _cors_response("", status=200) # HTMX outerHTML swap removes the card

async def update_settings(user_id: int, request, db: SupabaseDB):
    """Securely updates user preferences."""
    try:
        form = await request.formData()
        start = form.get("active_hours_start", "08:00")
        end = form.get("active_hours_end", "22:00")
        threshold = int(form.get("escalation_threshold", 60))
    except Exception:
        return _cors_response("Invalid data", status=400)
        
    # Secure server-side update
    try:
        await db._patch("users", {"user_id": f"eq.{user_id}"}, {
            "active_hours_start": start,
            "active_hours_end": end,
            "escalation_threshold": threshold
        })
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        return _cors_response("Database error", status=500)
        
    return _cors_response("OK", status=200)
