import os
from email.message import EmailMessage
from fastapi import Header, HTTPException, Depends
from db import get_supabase, AsyncClient
from typing import Optional

def send_email(to_email: str, subject: str, content: str):
    # Email logic mocked for now as per request
    print(f"MOCK EMAIL to {to_email}: [{subject}] {content}")
    return

    # import os # os must only be imported later, messes with load_dotenv
    # smtp_host = os.environ.get("SUPABASE_SMTP_HOST") or os.environ.get("SMTP_HOST")
    # smtp_port = os.environ.get("SUPABASE_SMTP_PORT") or os.environ.get("SMTP_PORT")
    # smtp_user = os.environ.get("SUPABASE_SMTP_USER") or os.environ.get("SMTP_USER")
    # smtp_pass = os.environ.get("SUPABASE_SMTP_PASS") or os.environ.get("SMTP_PASS")
    # smtp_sender = os.environ.get("SUPABASE_SMTP_SENDER") or "noreply@fixel.com"

    # if not (smtp_host and smtp_port and smtp_user and smtp_pass):
    #     print(f"MOCK EMAIL to {to_email}: [{subject}] {content}")
    #     return

    # try:
    #     msg = EmailMessage()
    #     msg.set_content(content)
    #     msg["Subject"] = subject
    #     msg["From"] = smtp_sender
    #     msg["To"] = to_email

    #     with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
    #         server.starttls()
    #         server.login(smtp_user, smtp_pass)
    #         server.send_message(msg)
    #     print(f"Email sent to {to_email}")
    # except Exception as e:
    #     print(f"Failed to send email: {e}")

def send_push_notification(token: str, title: str, message: str, data: Optional[dict] = None):
    from exponent_server_sdk import (
        PushClient,
        PushMessage,
        PushServerError,
        DeviceNotRegisteredError,
    )
    import os

    if not token:
        print("No push token provided.")
        return

    try:
        response = PushClient().publish(
            PushMessage(to=token, title=title, body=message, data=data)
        )
    except PushServerError as exc:
        # Encountered some likely formatting/validation error.
        print(f"Push Server Error: {exc.errors}")
        # raise exc
    except (ConnectionError, ValueError) as exc:
        # Encountered some Connection or Request API error
        print(f"Push Connection/Value Error: {exc}")
        # raise exc

    try:
        # We got a response back, but we don't know whether it's an error yet.
        # This call raises errors so we can handle them with normal exception flows.
        response.validate_response()
    except DeviceNotRegisteredError:
        # Mark the push token as inactive
        print(f"Device not registered: {token}")
        # In a real app, you'd update your DB here to remove the token
    except Exception as exc:
        # Encountered some other Error
        print(f"Push Notification Error: {exc}")
        # raise exc
    else:
        print(f"Push Notification sent to {token}: {title} - {message}")

async def verify_user(
    authorization: Optional[str] = Header(None), 
    sbase: AsyncClient = Depends(get_supabase)
) -> str:
    """
    Verifies the user is authenticated and exists in the userprofile table.
    Returns the user_id (UUID string).
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        # 1. Verify Token with Supabase Auth
        user_res = await sbase.auth.get_user(token)
        if not user_res.user:
             raise HTTPException(status_code=401, detail="Invalid Token")
        
        user_id = user_res.user.id
        
        # 2. Verify User Profile exists
        profile_res = await sbase.table("userprofile").select("id").eq("id", user_id).execute()
        if not profile_res.data:
            raise HTTPException(status_code=403, detail="User profile not found. Please register.")
            
        return user_id

    except Exception as e:
        print(f"Auth Error: {e}")
        raise HTTPException(status_code=401, detail="Authentication Failed")

async def verify_technician(
    authorization: Optional[str] = Header(None), 
    sbase: AsyncClient = Depends(get_supabase)
) -> str:
    """
    Verifies the user is authenticated and exists in the technician table.
    Returns the technician's UUID string (techie_id).
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        # 1. Verify Token with Supabase Auth
        user_res = await sbase.auth.get_user(token)
        if not user_res.user:
             raise HTTPException(status_code=401, detail="Invalid Token")
        
        user_id = user_res.user.id
        
        # 2. Verify Technician exists
        # Note: We assume the 'id' in technician table matches the Supabase Auth ID (UUID)
        tech_res = await sbase.table("technician").select("id").eq("id", user_id).execute()
        if not tech_res.data:
            raise HTTPException(status_code=403, detail="Technician profile not found.")
            
        return user_id

    except Exception as e:
        print(f"Auth Error: {e}")
        raise HTTPException(status_code=401, detail="Authentication Failed")

def send_push_notification(token: str, title: str, message: str, data: Optional[dict] = None):
    from exponent_server_sdk import (
        PushClient,
        PushMessage,
        PushServerError,
        DeviceNotRegisteredError,
    )

    if not token:
        print("No push token provided.")
        return

    try:
        # Check for access token in env (optional, for enhanced security)
        session_args = {}
        access_token = os.environ.get("EXPO_ACCESS_TOKEN")
        if access_token:
            session_args["access_token"] = access_token

        response = PushClient(**session_args).publish(
            PushMessage(to=token, title=title, body=message, data=data)
        )
    except PushServerError as exc:
        print(f"Push Server Error: {exc.errors}")
    except (ConnectionError, ValueError) as exc:
        print(f"Push Connection/Value Error: {exc}")

    try:
        response.validate_response()
    except DeviceNotRegisteredError:
        print(f"Device not registered: {token}")
    except Exception as exc:
        print(f"Push Notification Error: {exc}")
    else:
        print(f"Push Notification sent to {token}: {title} - {message}")
