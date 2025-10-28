# Systemd Service Setup for Skymarshal

This document describes the systemd services configured for Skymarshal and Litemarshal web interfaces.

## Services

Both services are now configured to run automatically at boot and restart on failure.

### Skymarshal Service

**Service Name**: `skymarshal.service`
**Port**: 5051
**Public URL**: https://dr.eamer.dev/skymarshal/

```bash
# Service management
sudo systemctl status skymarshal
sudo systemctl restart skymarshal
sudo systemctl stop skymarshal
sudo systemctl start skymarshal

# View logs
sudo journalctl -u skymarshal -f
```

### Litemarshal Service

**Service Name**: `litemarshal.service`
**Port**: 5050
**Public URL**: https://dr.eamer.dev/litemarshal/

```bash
# Service management
sudo systemctl status litemarshal
sudo systemctl restart litemarshal
sudo systemctl stop litemarshal
sudo systemctl start litemarshal

# View logs
sudo journalctl -u litemarshal -f
```

## Service Configuration

Both services are located at:
- `/etc/systemd/system/skymarshal.service`
- `/etc/systemd/system/litemarshal.service`

Key features:
- **Auto-restart**: Services automatically restart on failure
- **RestartSec=10**: 10-second delay between restart attempts
- **Journald logging**: Logs accessible via `journalctl`
- **User**: Runs as `coolhand` user
- **WorkingDirectory**: `/home/coolhand/projects/tools_bluesky/skymarshal`

## Authentication Features

Both apps now accept regular Bluesky passwords with warnings:

### Password Handling
- **App passwords** (recommended): Standard 19-character format `xxxx-xxxx-xxxx-xxxx`
- **Regular passwords** (allowed with warning): Users can authenticate but will see a security warning

### Warning Message
When a regular password is detected, users see:
> ⚠️ Warning: You appear to be using your regular Bluesky password. For security, we recommend using an app password from Settings > Privacy & Security > App Passwords.

### Session Tracking
- Sessions track whether a regular password was used via `session['used_regular_password']`
- Warning persists in session for Litemarshal: `session['password_warning']`

## Files Modified

1. **app.py** (Skymarshal):
   - Modified login endpoint to accept regular passwords with warnings
   - Added `used_regular_password` session flag
   - Returns warning in JSON response on successful login

2. **lite_app.py** (Litemarshal):
   - Added `_is_likely_regular_password()` function
   - Modified login endpoint to accept regular passwords with warnings
   - Stores warning message in session for display

3. **lite_app.py templates** (Litemarshal):
   - `templates/lite_login.html` - Updated with warning display support
   - `templates/lite_dashboard.html` - Added session password warning display
   - `static/css/lite.css` - Complete CSS redesign with modern dark theme

4. **Service files created**:
   - `/etc/systemd/system/skymarshal.service`
   - `/etc/systemd/system/litemarshal.service`
   - `/home/coolhand/projects/tools_bluesky/skymarshal/skymarshal/web/run_lite.py` (launcher)

## Caddy Configuration

Both services are proxied through Caddy with the following configuration:

```caddyfile
# Litemarshal
handle_path /litemarshal* {
    reverse_proxy localhost:5050
}

# Skymarshal
handle_path /skymarshal/* {
    reverse_proxy localhost:5051
}
```

## Flask Configuration

Both apps use `PrefixMiddleware` to handle subpath routing:

```python
class PrefixMiddleware:
    def __init__(self, app, prefix=''):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        if self.prefix:
            environ['SCRIPT_NAME'] = self.prefix
            if environ['PATH_INFO'].startswith(self.prefix):
                environ['PATH_INFO'] = environ['PATH_INFO'][len(self.prefix):]
        return self.app(environ, start_response)

# Applied as:
app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix='/skymarshal')  # or '/litemarshal'
```

## Troubleshooting

### Services won't start
```bash
# Check service status
sudo systemctl status skymarshal litemarshal

# View recent logs
sudo journalctl -u skymarshal -n 50
sudo journalctl -u litemarshal -n 50

# Reload service files after changes
sudo systemctl daemon-reload
sudo systemctl restart skymarshal litemarshal
```

### URL not accessible
```bash
# Test direct port access
curl -I http://localhost:5050/
curl -I http://localhost:5051/

# Test through proxy
curl -I https://dr.eamer.dev/litemarshal/
curl -I https://dr.eamer.dev/skymarshal/

# Check Caddy status
sudo systemctl status caddy
```

### Reset services
```bash
# Stop both services
sudo systemctl stop skymarshal litemarshal

# Disable auto-start
sudo systemctl disable skymarshal litemarshal

# Re-enable and start
sudo systemctl enable skymarshal litemarshal
sudo systemctl start skymarshal litemarshal
```

## Production Recommendations

For production deployment, consider:

1. **Use Gunicorn instead of Flask dev server**:
   ```bash
   ExecStart=/usr/bin/gunicorn -w 4 -b 0.0.0.0:5051 --chdir /home/coolhand/projects/tools_bluesky/skymarshal/skymarshal/web app:app
   ```

2. **Enable HTTPS session cookies**:
   ```python
   app.config['SESSION_COOKIE_SECURE'] = True
   ```

3. **Set up log rotation** for journald logs

4. **Monitor service health** with monitoring tools

5. **Regular security audits** for password handling

## References

- [Systemd Service Documentation](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [Flask Behind a Proxy](https://flask.palletsprojects.com/en/2.3.x/deploying/proxy_fix/)
- [Bluesky App Passwords](https://bsky.app/settings/app-passwords)
