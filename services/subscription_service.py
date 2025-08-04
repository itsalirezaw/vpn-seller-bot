from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse
from datetime import datetime
from sqlalchemy import select
from database.database import async_session
from database.models import Subscription
import html
import base64

app = FastAPI(title="Subscription Service")

BROWSER_KEYWORDS = ["Mozilla", "Chrome", "Safari", "Edge", "Firefox"]

@app.get("/sub/{token}")
async def serve_subscription(token: str, request: Request, raw: bool = False):
    """Return subscription content.

    If `raw` query param is set or the request is NOT from a browser, returns plain text (Base64 list).
    Otherwise renders a minimal HTML page showing subscription info and a copy link.
    """
    async with async_session() as session:
        result = await session.execute(select(Subscription).where(Subscription.token == token))
        sub: Subscription | None = result.scalar_one_or_none()

    if not sub:
        raise HTTPException(status_code=404, detail="Token not found")

    if sub.expire_at and sub.expire_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Token expired")

    # --- Generate content dynamically ---
    from services.account_manager import AccountManager
    account_manager = AccountManager()

    # Fetch account via AccountManager to avoid DetachedInstanceError
    account = await account_manager.get_account_by_id(sub.account_id) if hasattr(sub, 'account_id') else None
    if not account:
        raise HTTPException(status_code=404, detail="Account not found for token")

    configs = await account_manager.generate_config_urls(account.uuid)

    if not configs:
        raise HTTPException(status_code=500, detail="No configs available for this account")

    all_urls = [url for srv in configs.values() for url in srv.values()]
    subscription_b64 = base64.b64encode("\n".join(all_urls).encode()).decode()

    # Decide response type
    if raw:
        return PlainTextResponse(subscription_b64)

    ua = request.headers.get("User-Agent", "")
    is_browser = any(k in ua for k in BROWSER_KEYWORDS)

    if not is_browser:
        return PlainTextResponse(subscription_b64)

    raw_link = str(request.url.include_query_params(raw="1"))
    preview = html.escape(subscription_b64[:200] + ("..." if len(subscription_b64) > 200 else ""))
    html_body = f"""
    <!DOCTYPE html>
    <html lang=\"en\"><head><meta charset=\"utf-8\"><title>Subscription</title>
    <style>body{{font-family:Arial;color:#ddd;background:#111;padding:2rem}} pre{{background:#222;padding:1rem;border-radius:6px;overflow:auto}}</style></head>
    <body>
      <h2>VPN Subscription</h2>
      <p>Use the following link in your VPN client:</p>
      <pre>{html.escape(raw_link)}</pre>
      <button onclick=\"navigator.clipboard.writeText('{html.escape(raw_link)}');alert('Copied');\">Copy</button>
      <h3>Preview</h3>
      <pre>{preview}</pre>
    </body></html>"""
    return HTMLResponse(html_body) 