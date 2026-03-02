# Key Pool API

LRU key rotation with rate-limit cooldown.

## Classes

### `KeyPool`

Manages a pool of API keys with LRU rotation.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `keys` | `list[str]` | List of API keys |
| `cooldown_seconds` | `int` | Cooldown after rate limit (default: 300) |

**Attributes:**

| Name | Type | Description |
|------|------|-------------|
| `available` | `int` | Number of available (non-cooldown) keys |
| `total` | `int` | Total number of keys |

---

## Methods

### `get_key()`

Get the least-recently-used available key.

**Returns:**

- `str`: API key
- `None`: If no keys available

**Example:**

```python
from gasclaw.kimigas.key_pool import KeyPool

pool = KeyPool(["sk-key1", "sk-key2", "sk-key3"])
key = pool.get_key()
if key:
    use_key_for_request(key)
```

---

### `report_rate_limit(key)`

Report that a key hit a rate limit.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `key` | `str` | The rate-limited key |

**Behavior:**

- Moves key to cooldown queue
- Key unavailable for `cooldown_seconds`

**Example:**

```python
response = make_api_request(key)
if response.status_code == 429:
    pool.report_rate_limit(key)
    # Get a different key
    new_key = pool.get_key()
```

---

### `is_available(key)`

Check if a key is currently available.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `key` | `str` | Key to check |

**Returns:**

- `bool`: True if key is available

---

## Example Usage

```python
from gasclaw.kimigas.key_pool import KeyPool

# Create pool with 5-minute cooldown
pool = KeyPool(
    keys=["sk-1", "sk-2", "sk-3"],
    cooldown_seconds=300
)

# Get key for request
key = pool.get_key()
if not key:
    raise Exception("No keys available")

# Make request
response = requests.post(
    "https://api.example.com/v1/chat",
    headers={"Authorization": f"Bearer {key}"}
)

# Handle rate limit
if response.status_code == 429:
    pool.report_rate_limit(key)
    # Will get different key next time
```
