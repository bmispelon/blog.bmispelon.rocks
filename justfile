@default:
    just --list

# Start a webserver on the given port
serve port='8888':
    python -m webbrowser -t http://localhost:{{port}}
    python -m http.server -d blog {{port}}

# Run the `prettier` formatter on the blog's content (committed files only)
prettier:
    git ls-files -x vendors blog/ | grep -v /vendors/ | grep -E '\.(html|css|js)$' | xargs prettier -w

# Generate CSS rules for header variants
headervariants:
    #!/usr/bin/env bash
    i=1
    for x in `ls blog/static/css/images/headers/*.jpeg`
    do
        xx=$(basename $x)
        xxx=${xx%.*}

        echo "header.variant$i {"
        echo "  --header-image-jpeg: url(\"./images/headers/$xxx.jpeg\");"
        echo "  --header-image-avif: url(\"./images/headers/$xxx.avif\");"
        echo "  --header-image-webp: url(\"./images/headers/$xxx.webp\");"
        echo "}"
        ((i++))
    done

# call the blog engine script bbblog.py
blog *a:
    python bbblog.py {{a}}
