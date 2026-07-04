# How to Reduce API Token Costs When Using Bob

This guide provides practical strategies to minimize API token consumption while working with Bob, your AI coding assistant.

## Understanding Token Usage

Bob uses tokens for:
- Reading your messages and context
- Processing file contents
- Generating responses
- Analyzing code and documentation

Your current token budget: **200,000 tokens**

## Key Strategies to Reduce Costs

### 1. **Be Specific and Concise in Your Requests**

❌ **Avoid:**
```
"Can you help me understand what's going on with my code and maybe fix some issues if you find any?"
```

✅ **Better:**
```
"Fix the TypeError in calculate_total() function in calculations.py line 45"
```

**Why it works:** Specific requests help Bob focus on exactly what you need, avoiding unnecessary file exploration and analysis.

### 2. **Use Targeted File Reading**

❌ **Avoid:** Asking Bob to "review all files" or "check the entire codebase"

✅ **Better:** 
- Point to specific files: "Review the authentication logic in [`auth.py`](auth.py)"
- Use line ranges: "Check lines 100-150 in [`main.py`](main.py)"

**Why it works:** Bob can read specific portions of files using line ranges, dramatically reducing token consumption.

### 3. **Leverage .bobignore File**

Create a `.bobignore` file in your project root to exclude:
- Large data files (`.db`, `.csv`, `.json` data dumps)
- Binary files (images, videos, compiled code)
- Dependencies (`node_modules/`, `venv/`, `.git/`)
- Build artifacts (`dist/`, `build/`, `__pycache__/`)

**Example .bobignore:**
```
# Data files
data/*.db
data/*.csv
*.sqlite

# Dependencies
node_modules/
venv/
.venv/

# Build artifacts
dist/
build/
__pycache__/
*.pyc

# Large logs
*.log
logs/

# Media files
*.mp4
*.mov
*.png
*.jpg
```

**Why it works:** Prevents Bob from accidentally reading large files that aren't relevant to code tasks.

### 4. **Break Down Complex Tasks**

❌ **Avoid:**
```
"Build a complete authentication system with login, registration, password reset, 
email verification, 2FA, session management, and admin dashboard"
```

✅ **Better:**
```
Task 1: "Create user registration endpoint with email validation"
Task 2: "Add password hashing and storage"
Task 3: "Implement login with JWT tokens"
... (continue step by step)
```

**Why it works:** Smaller tasks require less context and fewer iterations, reducing overall token usage.

### 5. **Provide Context Efficiently**

Instead of asking Bob to discover everything:

✅ **Provide key information upfront:**
```
"I'm using Python 3.11 with FastAPI. The database models are in models/user.py. 
Add a new 'email_verified' boolean field to the User model."
```

**Why it works:** Reduces exploration time and file reading.

### 6. **Use Code Mode for Implementation**

- **💻 Code Mode**: Best for writing/editing code (no browser/MCP tools = fewer tokens)
- **🛠️ Advanced Mode**: Only when you need browser automation or MCP servers
- **📝 Plan Mode**: For planning before implementation (cheaper than trial-and-error coding)

**Why it works:** Different modes have different tool access, affecting token consumption.

### 7. **Avoid Redundant Requests**

❌ **Avoid:**
```
"Show me the file"
(Bob shows file)
"Now explain what it does"
(Bob reads file again)
"Now fix the bug"
(Bob reads file again)
```

✅ **Better:**
```
"Read auth.py, explain the authentication flow, and fix the session timeout bug"
```

**Why it works:** Single comprehensive request vs. multiple round-trips.

### 8. **Use Search Instead of Reading Multiple Files**

When looking for something across files:

✅ **Use search_files:**
```
"Search for all TODO comments in the src/ directory"
```

Instead of:
❌ "Read all files in src/ and find TODOs"

**Why it works:** Search is more efficient than reading entire files.

### 9. **Limit File Exploration**

❌ **Avoid:** "Explore the project structure"

✅ **Better:** "List files in the src/components/ directory"

**Why it works:** Targeted exploration uses fewer tokens than recursive directory listings.

### 10. **Review Before Asking Bob**

Before asking Bob to review code:
1. Run your linter locally
2. Check for obvious syntax errors
3. Test basic functionality

**Why it works:** Reduces back-and-forth iterations for simple issues you can catch yourself.

## Advanced Optimization Techniques

### Use Plan Mode First

For complex features:
1. **📝 Plan Mode**: Design the solution (low token cost)
2. **💻 Code Mode**: Implement based on the plan (focused, efficient)

### Batch Related Changes

Instead of:
- "Add logging to function A"
- "Add logging to function B"  
- "Add logging to function C"

Do:
- "Add logging to functions A, B, and C in utils.py"

### Provide File Contents Directly

If you already have a file open:
```
"Here's the content of config.py:
[paste content]

Update the API_TIMEOUT to 30 seconds"
```

**Why it works:** Bob doesn't need to use read_file tool.

## Monitoring Your Usage

- Check the "Current Cost" in environment details
- Your budget: 200,000 tokens
- Track costs per session to identify patterns

## Example: Efficient vs. Inefficient Workflow

### ❌ Inefficient (High Token Cost)
```
User: "Something is broken"
Bob: [Reads 20 files to understand context]
User: "It's in the login function"
Bob: [Reads login-related files]
User: "The password validation specifically"
Bob: [Finally focuses on the issue]
```

### ✅ Efficient (Low Token Cost)
```
User: "The password validation in auth/login.py line 67 is rejecting valid passwords 
with special characters. Fix the regex pattern."
Bob: [Reads specific file, fixes issue immediately]
```

## Quick Reference Checklist

Before each Bob request, ask yourself:

- [ ] Is my request specific and clear?
- [ ] Have I identified the relevant files?
- [ ] Can I provide line numbers or function names?
- [ ] Is my .bobignore configured properly?
- [ ] Am I using the right mode for this task?
- [ ] Could I batch this with other related requests?

## Conclusion

Efficient Bob usage is about **precision over exploration**. The more specific and targeted your requests, the fewer tokens you'll consume while getting better results faster.

Remember: Bob is most cost-effective when you guide it directly to what needs attention, rather than asking it to discover issues through broad exploration.