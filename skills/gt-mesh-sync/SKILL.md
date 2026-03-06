# GT Mesh Sync Skill

Skill for connecting Gasclaw to GT Mesh collaborative network.

## What is GT Mesh?

GT Mesh connects multiple Gas Town/Gasclaw instances into a collaborative coding network. Share skills, collaborate on code, distribute work across nodes.

## Installation

```bash
# From gasclaw directory
gt skill install Deepwork-AI/gt-mesh

# Or manually
cp -r skills/gt-mesh-sync/* ~/.gasclaw/skills/
```

## Configuration

Create `~/.gasclaw/mesh.yaml`:

```yaml
version: 1
instance:
  id: "gasclaw-worker-001"
  name: "My Gasclaw"
  role: "worker"

dolthub:
  org: "deepwork"
  database: "gt-mesh-mail"
```

## Commands

| Command | Description |
|---------|-------------|
| `gt mesh init` | Join the mesh |
| `gt mesh status` | Show mesh dashboard |
| `gt mesh send` | Send message to node |
| `gt mesh inbox` | Read messages |
| `gt mesh sync` | Force sync |
| `gt mesh skills` | List shared skills |
| `gt mesh skill publish` | Share your skill |

## Links

- [GT Mesh Repo](https://github.com/Deepwork-AI/gt-mesh)
- [Full Documentation](https://github.com/Deepwork-AI/gt-mesh/blob/main/README.md)
