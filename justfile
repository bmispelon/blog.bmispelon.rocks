@default:
    just --list

# Start a webserver on the given port
serve port='8888':
    python -m webbrowser -t http://localhost:{{port}}
    python -m http.server -d blog {{port}}

# Run the `prettier` formatter on the blog's content (committed files only)
prettier:
    git ls-files -x vendors blog/ | grep -v /vendors/ | grep -E '\.(html|css|js)$' | xargs prettier -w

# call the blog engine script bbblog.py
blog *a:
    python bbblog.py {{a}}
