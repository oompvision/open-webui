# SSO Integration Guide

This document explains how to share authentication between the main AlumniHuddle app (Vercel) and the AI Chat service (Railway).

## Overview

Both apps use the same Supabase project for authentication, enabling seamless SSO:

```
┌─────────────────┐         ┌─────────────────┐
│  Main App       │         │  AI Chat        │
│  (Vercel)       │         │  (Railway)      │
│                 │         │                 │
│  alumnihuddle   │  SSO    │  chat.alumni    │
│  .vercel.app    │◄───────▶│  huddle.com     │
└────────┬────────┘         └────────┬────────┘
         │                           │
         │    Same Supabase Auth     │
         └───────────┬───────────────┘
                     ▼
         ┌─────────────────────┐
         │     Supabase        │
         │  - Auth (shared)    │
         │  - Database         │
         └─────────────────────┘
```

## How It Works

1. User logs in on main app → Supabase sets auth cookies
2. User clicks "Chat with Mentor Coach" → redirects to chat app
3. Chat app reads Supabase session → user is already logged in
4. User can chat without re-authenticating

## Implementation Options

### Option A: Cookie-Based SSO (Recommended for Same Domain)

If both apps are on the same root domain (e.g., `alumnihuddle.com` and `chat.alumnihuddle.com`):

1. **Configure Supabase cookie domain** in both apps:
   ```javascript
   // In Supabase client config
   const supabase = createClient(url, key, {
     auth: {
       cookieOptions: {
         domain: '.alumnihuddle.com',  // Note the leading dot
         sameSite: 'lax',
         secure: true
       }
     }
   })
   ```

2. **Both apps use the same Supabase project** (already configured)

3. **Session sharing** happens automatically via cookies

### Option B: Token-Based SSO (For Different Domains)

If apps are on different domains (e.g., `vercel.app` and `railway.app`):

1. **Main app generates a redirect token**:
   ```javascript
   // When user clicks "Open Chat"
   const session = await supabase.auth.getSession()
   const redirectUrl = `https://chat.alumnihuddle.com/auth/sso?token=${session.access_token}&huddle=${huddleSlug}`
   window.location.href = redirectUrl
   ```

2. **Chat app validates the token**:
   ```python
   # In chat app's SSO endpoint
   @app.get("/auth/sso")
   async def sso_login(token: str, huddle: str):
       # Verify token with Supabase
       user = supabase.auth.get_user(token)
       if user:
           # Create local session
           # Redirect to chat
           pass
   ```

### Option C: OAuth Flow (Most Secure)

Use Supabase as the OAuth provider:

1. **Main app initiates OAuth**:
   ```javascript
   // Redirect to chat with OAuth
   const { data, error } = await supabase.auth.signInWithOAuth({
     provider: 'custom',
     options: {
       redirectTo: 'https://chat.alumnihuddle.com/auth/callback'
     }
   })
   ```

2. **Chat app handles callback** and exchanges code for session

## Current Implementation

The chat app currently supports:

1. **Direct Supabase Auth** - Users can log in directly on chat app
2. **Shared Database** - Users created on main app exist in chat app
3. **Huddle Detection** - Extracts huddle from subdomain/path/header

### To Enable Full SSO

Add this endpoint to the chat app (`backend/open_webui/routers/auths.py`):

```python
@router.get("/sso")
async def sso_redirect(
    token: str = Query(...),
    huddle: str = Query(...),
    request: Request
):
    """
    Handle SSO redirect from main app.
    Validates Supabase token and creates local session.
    """
    try:
        # Verify token with Supabase
        from supabase import create_client
        supabase = create_client(
            os.environ['SUPABASE_URL'],
            os.environ['SUPABASE_SERVICE_KEY']
        )

        user_response = supabase.auth.get_user(token)
        if not user_response.user:
            raise HTTPException(401, "Invalid token")

        user_email = user_response.user.email

        # Find or create user in OpenWebUI
        user = Users.get_user_by_email(user_email)
        if not user:
            # Create user with huddle assignment
            user = Users.insert_new_user(...)

        # Create JWT for OpenWebUI session
        jwt_token = create_token(
            data={"id": user.id},
            expires_delta=timedelta(days=7)
        )

        # Redirect to chat with session cookie
        response = RedirectResponse(url=f"/{huddle}")
        response.set_cookie(
            key="token",
            value=jwt_token,
            httponly=True,
            secure=True,
            samesite="lax"
        )
        return response

    except Exception as e:
        log.error(f"SSO error: {e}")
        raise HTTPException(401, "SSO authentication failed")
```

## Main App Integration

Add a "Chat with Mentor Coach" button to the main app:

```javascript
// React component example
function ChatButton({ huddleSlug }) {
  const handleClick = async () => {
    const { data: { session } } = await supabase.auth.getSession()

    if (session) {
      // User is logged in - redirect with token for SSO
      const chatUrl = `https://chat.alumnihuddle.com/auth/sso?token=${session.access_token}&huddle=${huddleSlug}`
      window.open(chatUrl, '_blank')
    } else {
      // User not logged in - redirect to chat login
      window.open(`https://chat.alumnihuddle.com/${huddleSlug}`, '_blank')
    }
  }

  return (
    <button onClick={handleClick}>
      Chat with Mentor Coach
    </button>
  )
}
```

## Security Considerations

1. **Token Expiry**: Supabase access tokens expire (default: 1 hour)
2. **HTTPS Only**: All SSO redirects must use HTTPS
3. **CORS**: Configure CORS to allow requests between domains
4. **Token Validation**: Always validate tokens server-side

## Testing SSO

1. Log in to main app at `alumnihuddle.vercel.app`
2. Click "Chat with Mentor Coach" button
3. Should redirect to `chat.alumnihuddle.com/{huddle}`
4. Should be automatically logged in
5. User info should match main app

## Troubleshooting

### "Invalid token" error
- Token may have expired - get a fresh token
- Check that both apps use the same Supabase project

### User not found
- Ensure user was created with matching email
- Check huddle assignment in users table

### CORS errors
- Add chat domain to main app's CORS config
- Add main app domain to chat's CORS_ALLOW_ORIGIN

### Cookie not shared
- Ensure both apps are on same root domain
- Check cookie domain is set to `.alumnihuddle.com`
- Verify secure and sameSite settings
