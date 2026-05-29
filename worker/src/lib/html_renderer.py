"""
lib/html_renderer.py — Renders server-side HTML partials for HTMX.
Follows a clean, Material Design-inspired aesthetic (Android-like UI).
"""
import urllib.parse
from datetime import datetime

def escape_html(text: str) -> str:
    """Basic HTML escaping to prevent XSS."""
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def render_task_card(task: dict, tz_str: str) -> str:
    """Renders a single task as a beautifully styled Material Design card."""
    title = escape_html(task.get("title", "Untitled"))
    desc = escape_html(task.get("description", ""))
    
    # Parse deadline for display
    deadline = task.get("deadline")
    if isinstance(deadline, str):
        try:
            deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        except Exception:
            deadline = None
            
    dl_str = deadline.strftime("%Y-%m-%d %H:%M") if deadline else "No deadline"
    
    # Extract reminder info
    reminders = task.get("reminders", [])
    freq_str = "No reminder"
    if reminders:
        r = reminders[0]
        freq_str = f"Every {r.get('frequency_value', '')} {r.get('frequency_type', '')}"
        
    user_task_id = task.get("user_task_id")
    is_completed = task.get("completed", False)
    
    status_color = "text-green-500" if is_completed else "text-cyan-500"
    
    html = f"""
    <div id="task-card-{user_task_id}" class="bg-[#1e293b] rounded-2xl shadow-md border border-slate-700/50 p-5 mb-4 transition-all hover:shadow-lg relative overflow-hidden group">
        <div class="flex justify-between items-start">
            <div class="flex-1 pr-4">
                <h3 class="font-bold text-lg text-slate-100 leading-tight mb-1">{title}</h3>
                """
    if desc:
        html += f'<p class="text-sm text-slate-400 mb-3 line-clamp-2">{desc}</p>'
        
    html += f"""
                <div class="flex items-center gap-3 text-xs text-slate-400 font-medium">
                    <span class="flex items-center gap-1 bg-slate-800/80 py-1 px-2 rounded-lg">
                        <svg class="w-3.5 h-3.5 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                        {dl_str}
                    </span>
                    <span class="flex items-center gap-1 bg-slate-800/80 py-1 px-2 rounded-lg">
                        <svg class="w-3.5 h-3.5 {status_color}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path></svg>
                        {freq_str}
                    </span>
                </div>
            </div>
            
            <div class="flex flex-col gap-2 items-center justify-center opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
    """
    
    if not is_completed:
        html += f"""
                <button hx-post="/api/tasks/{user_task_id}/done" 
                        hx-target="#task-card-{user_task_id}" hx-swap="outerHTML" 
                        hx-credentials="include"
                        class="w-10 h-10 rounded-full bg-green-500/10 text-green-400 hover:bg-green-500 hover:text-slate-900 flex items-center justify-center transition-colors shadow-sm"
                        aria-label="Mark done" title="Mark done">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"></path></svg>
                </button>
        """
        
    html += f"""
                <button hx-delete="/api/tasks/{user_task_id}" 
                        hx-target="#task-card-{user_task_id}" hx-swap="outerHTML swap:300ms" 
                        hx-credentials="include"
                        class="w-10 h-10 rounded-full bg-red-500/10 text-red-400 hover:bg-red-500 hover:text-slate-900 flex items-center justify-center transition-colors shadow-sm"
                        aria-label="Delete task" title="Delete task">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                </button>
            </div>
        </div>
    </div>
    """
    return html

def render_task_list(tasks: list, tz_str: str, empty_msg: str = "No tasks found in this category.") -> str:
    if not tasks:
        return f"""
        <div class="text-center py-12 px-4 bg-[#1e293b]/50 rounded-2xl border border-slate-700/50 border-dashed">
            <svg class="w-16 h-16 text-slate-600 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path></svg>
            <p class="text-slate-400 font-medium">{empty_msg}</p>
        </div>
        """
    return "".join(render_task_card(t, tz_str) for t in tasks)

def render_add_task_form() -> str:
    return """
    <form hx-post="/api/tasks" hx-target="#task-feed" hx-swap="afterbegin"
          hx-credentials="include"
          hx-on::after-request="if(event.detail.successful) this.reset()"
          class="bg-[#1e293b] border border-slate-700/50 rounded-2xl p-5 sm:p-6 shadow-md mb-8">
      
      <div class="mb-4">
        <label class="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 ml-1">Task Title</label>
        <input name="title" placeholder="What needs to be done?" required
               class="w-full bg-slate-900/50 border border-slate-700/80 rounded-xl px-4 py-3 text-slate-100 placeholder-slate-500
                      focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 focus:outline-none transition-all shadow-inner" />
      </div>
      
      <div class="mb-5">
        <label class="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 ml-1">Description (Optional)</label>
        <textarea name="description" placeholder="Any details?" rows="2"
               class="w-full bg-slate-900/50 border border-slate-700/80 rounded-xl px-4 py-3 text-slate-100 placeholder-slate-500
                      focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 focus:outline-none transition-all shadow-inner resize-none"></textarea>
      </div>
      
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        <div>
            <label class="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 ml-1">Deadline</label>
            <input name="deadline" type="datetime-local" required
                   class="w-full bg-slate-900/50 border border-slate-700/80 rounded-xl px-4 py-3 text-slate-100
                          focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 focus:outline-none transition-all shadow-inner [color-scheme:dark]" />
        </div>
        <div>
            <label class="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 ml-1">Reminder Frequency</label>
            <select name="frequency"
                    class="w-full bg-slate-900/50 border border-slate-700/80 rounded-xl px-4 py-3 text-slate-100
                           focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 focus:outline-none transition-all shadow-inner appearance-none">
              <option value="15m">Every 15 minutes</option>
              <option value="30m" selected>Every 30 minutes</option>
              <option value="1h">Every hour</option>
              <option value="2h">Every 2 hours</option>
              <option value="4h">Every 4 hours</option>
              <option value="daily">Daily</option>
            </select>
        </div>
      </div>
      
      <button type="submit"
              class="w-full py-3.5 rounded-xl font-bold text-slate-900
                     bg-gradient-to-r from-cyan-400 to-cyan-500 hover:from-cyan-300 hover:to-cyan-400 
                     focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-slate-900
                     transition-all shadow-lg shadow-cyan-500/25 active:scale-[0.98] flex items-center justify-center gap-2">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path></svg>
        Create Task
      </button>
    </form>
    """

def render_settings_form(timezone: str, start: str, end: str, threshold: int) -> str:
    start_val = escape_html(start or "08:00")
    end_val = escape_html(end or "22:00")
    thresh_val = escape_html(str(threshold or 60))
    tz_val = escape_html(timezone or "UTC")
    
    return f"""
    <form hx-patch="/api/settings" hx-swap="none" hx-credentials="include"
          class="bg-[#1e293b] border border-slate-700/50 rounded-2xl p-6 sm:p-8 shadow-md">
      
      <div id="settings-feedback" class="hidden mb-6 p-4 rounded-xl font-medium text-sm transition-all"></div>
      
      <div class="mb-6">
        <label class="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 ml-1">Timezone</label>
        <p class="text-xs text-slate-500 mb-2 ml-1">Currently set to: <strong class="text-slate-300">{tz_val}</strong>. To change, use the Telegram bot's /timezone command for GPS auto-detection.</p>
        <input disabled value="{tz_val}"
               class="w-full bg-slate-900/30 border border-slate-700/50 rounded-xl px-4 py-3 text-slate-400 cursor-not-allowed shadow-inner" />
      </div>
      
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-6">
        <div>
          <label class="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 ml-1">Active Hours Start</label>
          <input type="time" name="active_hours_start" value="{start_val}" required
                 class="w-full bg-slate-900/50 border border-slate-700/80 rounded-xl px-4 py-3 text-slate-100
                        focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 focus:outline-none transition-all shadow-inner [color-scheme:dark]" />
        </div>
        <div>
          <label class="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 ml-1">Active Hours End</label>
          <input type="time" name="active_hours_end" value="{end_val}" required
                 class="w-full bg-slate-900/50 border border-slate-700/80 rounded-xl px-4 py-3 text-slate-100
                        focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 focus:outline-none transition-all shadow-inner [color-scheme:dark]" />
        </div>
      </div>
      
      <div class="mb-8">
        <label class="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 ml-1">Escalation Threshold (minutes)</label>
        <p class="text-xs text-slate-500 mb-2 ml-1">Reminders double in frequency when the deadline is this close.</p>
        <input type="number" name="escalation_threshold" value="{thresh_val}" min="10" max="1440" required
               class="w-full bg-slate-900/50 border border-slate-700/80 rounded-xl px-4 py-3 text-slate-100
                      focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 focus:outline-none transition-all shadow-inner" />
      </div>
      
      <button type="submit" onclick="document.getElementById('settings-feedback').className='hidden mb-6 p-4 rounded-xl font-medium text-sm transition-all';"
              hx-on::after-request="
                const fb = document.getElementById('settings-feedback');
                fb.classList.remove('hidden');
                if(event.detail.successful) {{
                    fb.classList.add('bg-green-500/10', 'text-green-400', 'border', 'border-green-500/20');
                    fb.textContent = 'Settings saved securely.';
                }} else {{
                    fb.classList.add('bg-red-500/10', 'text-red-400', 'border', 'border-red-500/20');
                    fb.textContent = 'Failed to save settings.';
                }}
                setTimeout(() => fb.classList.add('hidden'), 3000);
              "
              class="w-full py-3.5 rounded-xl font-bold text-slate-900
                     bg-slate-200 hover:bg-white
                     focus:ring-2 focus:ring-slate-300 focus:ring-offset-2 focus:ring-offset-slate-900
                     transition-all shadow-lg shadow-white/10 active:scale-[0.98]">
        Save Security & Preferences
      </button>
    </form>
    """
