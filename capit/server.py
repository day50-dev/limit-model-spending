"""capit web server - Browser interface for capit.

Usage:
    capit serve              # Start server on default port 8080
    capit serve --port 9000  # Custom port
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from capit import (
    load_master_lookup,
    save_master_lookup,
    list_platforms,
    list_agents,
    get_platform_module,
    get_store_module,
    do_issue,
    ensure_capit_dir,
    prompt_for_master_key,
    get_master_key,
)

from flask import Flask, jsonify, request, render_template_string
from pathlib import Path

app = Flask(__name__, 
    template_folder=str(Path(__file__).parent / 'templates'),
    static_folder=str(Path(__file__).parent / 'static'),
    static_url_path='/static')


@app.route('/')
def index():
    template_path = Path(__file__).parent / 'templates' / 'index.html'
    platforms = list_platforms()
    agents = list_agents()
    lookup = load_master_lookup()
    configured = list(lookup.keys())
    content = template_path.read_text()
    return render_template_string(content, 
        platforms=platforms, 
        agents=agents,
        configured_platforms=configured
    )


@app.route('/api/issue', methods=['POST'])
def issue_key():
    data = request.get_json()
    platform = data.get('platform')
    spend_cap = data.get('spend_cap')
    agent = data.get('agent')
    prefix = data.get('prefix')
    confirmed = data.get('confirmed', False)

    if not platform or not spend_cap:
        return jsonify({'error': 'Platform and spend_cap required'}), 400

    try:
        key = do_issue(
            platform, 
            str(spend_cap),
            prefix=prefix,
            send_to=agent if agent else None,
            confirm=not confirmed
        )
        return jsonify({'key': key})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/issue/preview', methods=['POST'])
def preview_issue():
    data = request.get_json()
    platform = data.get('platform')
    spend_cap = data.get('spend_cap')
    agent = data.get('agent')

    if not platform or not spend_cap or not agent:
        return jsonify({'error': 'Platform, spend_cap, and agent required'}), 400

    try:
        from capit import get_agent_module
        agent_module = get_agent_module(agent)

        if not hasattr(agent_module, 'preview'):
            return jsonify({'error': f'Agent {agent} does not support preview'}), 400

        preview_data = agent_module.preview(platform, spend_cap, agent)
        preview_data['agent'] = agent
        preview_data['platform'] = platform
        preview_data['spend_cap'] = spend_cap
        return jsonify(preview_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/keys', methods=['GET'])
def list_keys():
    lookup = load_master_lookup()
    all_keys = []

    for platform, info in lookup.items():
        try:
            store_module = get_store_module(info["store"])
            master_key = store_module.retrieve_key(platform)
            if not master_key:
                continue
            platform_module = get_platform_module(platform)
            if not hasattr(platform_module, 'list_keys'):
                continue
            keys = platform_module.list_keys(master_key)
            for key in keys:
                all_keys.append({
                    'name': key.get('name', key.get('label', 'unnamed')),
                    'provider': platform,
                    'usage': key.get('usage', 0) or 0,
                    'limit': key.get('limit', 'unlimited'),
                    'created': key.get('created_at', '')[:10] if key.get('created_at') else '',
                    'id': key.get('id') or key.get('hash'),
                })
        except Exception:
            continue

    all_keys.sort(key=lambda k: k.get('name', '').lower())
    return jsonify(all_keys)


@app.route('/api/keys/delete', methods=['POST'])
def delete_key():
    data = request.get_json()
    pattern = data.get('pattern')
    
    if not pattern:
        return jsonify({'error': 'Pattern required'}), 400

    from capit import _parse_key_pattern
    lookup = load_master_lookup()
    matches = _parse_key_pattern(pattern, lookup)
    
    if not matches:
        return jsonify({'error': 'No matching keys'}), 404

    deleted_count = 0
    for platform, key_id, key_data in matches:
        try:
            store_module = get_store_module(lookup[platform]["store"])
            master_key = store_module.retrieve_key(platform)
            platform_module = get_platform_module(platform)
            if hasattr(platform_module, 'delete_key'):
                platform_module.delete_key(master_key, key_id)
                deleted_count += 1
        except Exception:
            pass

    return jsonify({'ok': True, 'deleted': deleted_count})


@app.route('/api/platforms/add', methods=['POST'])
def add_platform():
    data = request.get_json()
    platform = data.get('platform')
    master_key = data.get('master_key')

    if not platform or not master_key:
        return jsonify({'error': 'Platform and master_key required'}), 400

    try:
        ensure_capit_dir()
        stores = list_stores()
        default_store = "dotenv" if "dotenv" in stores else stores[0]
        store_module = get_store_module(default_store)
        store_module.store_key(platform, master_key)
        
        lookup = load_master_lookup()
        lookup[platform] = {"store": default_store}
        save_master_lookup(lookup)
        
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/platforms/remove', methods=['POST'])
def remove_platform():
    data = request.get_json()
    platform = data.get('platform')

    if not platform:
        return jsonify({'error': 'Platform required'}), 400

    lookup = load_master_lookup()
    if platform not in lookup:
        return jsonify({'error': 'Platform not configured'}), 400

    try:
        store_module = get_store_module(lookup[platform]["store"])
        store_module.delete_key(platform)
        del lookup[platform]
        save_master_lookup(lookup)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


def list_stores():
    """List all available stores."""
    from capit import list_modules as list_mods
    return list_mods(Path(__file__).parent / "stores")


def create_server(port=0, host='0.0.0.0'):
    """Start the capit web server. Returns the actual port.

    If the port is taken, increments until an available port is found.
    Port 0 means pick any available port from the OS.
    """
    import socket
    import sys

    max_attempts = 100
    for attempt in range(max_attempts):
        try:
            if port == 0:
                # Port 0: let OS pick any available port
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind((host, 0))
                port = s.getsockname()[1]
                s.close()
                break
            else:
                # Try the given port
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind((host, port))
                s.close()
                break
        except OSError as e:
            if e.errno == 98:  # Address already in use
                if port == 0:
                    # Retry with a random port
                    continue
                # Try the next port
                port += 1
                if port > 65535:
                    port = 1024
            else:
                raise

    print(f"capit web server running on http://{host}:{port}", file=sys.stderr)
    app.run(host=host, port=port, debug=False)
    return port


if __name__ == '__main__':
    create_server()