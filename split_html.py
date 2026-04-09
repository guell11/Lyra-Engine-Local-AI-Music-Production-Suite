import os
import re

html_path = r'c:\Users\guell\Documents\gerador de musica\templates\index.html'

with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Make directory
partials_dir = r'c:\Users\guell\Documents\gerador de musica\templates\partials'
os.makedirs(partials_dir, exist_ok=True)

# Define boundaries. Each page has a comment like <!-- ══════ PAGE: NAME ══════ -->
pages = [
    ("criar", r'<!-- ══════ PAGE: CRIAR ══════ -->(.*?)<!-- ══════ PAGE: FEED ══════ -->'),
    ("feed", r'<!-- ══════ PAGE: FEED ══════ -->(.*?)<!-- ══════ PAGE: CONFIG ══════ -->'),
    ("config", r'<!-- ══════ PAGE: CONFIG ══════ -->(.*?)<!-- ══════ PAGE: CHAT \(OPEN WEBUI CLONE\) ══════ -->'),
    ("chat", r'<!-- ══════ PAGE: CHAT \(OPEN WEBUI CLONE\) ══════ -->(.*?)<!-- Bottom Player -->')
]

for name, pattern in pages:
    match = re.search(pattern, content, flags=re.DOTALL)
    if match:
        html_block = match.group(1).strip()
        if name == "chat":
            # For chat, we don't want to replace "<!-- Bottom Player -->", we just extract the div.
            # But wait, looking at my regex, it captures everything until <!-- Bottom Player -->.
            # The last line of chat is </div> then some blank lines then </div> for page-container.
            pass
        
        # Save to file
        with open(os.path.join(partials_dir, f'page_{name}.html'), 'w', encoding='utf-8') as f:
            f.write(html_block)

        # We will replace in the original.
        # But wait, let's just do it manually if it's safer. Let's try replacing.
        replace_text = f"{{% include 'partials/page_{name}.html' %}}\n"
        
        # For simplicity in regex replacement, include the comments.
        if name == "criar":
            content = re.sub(r'<!-- ══════ PAGE: CRIAR ══════ -->.*?(?=<!-- ══════ PAGE: FEED ══════ -->)', replace_text, content, flags=re.DOTALL)
        elif name == "feed":
            content = re.sub(r'<!-- ══════ PAGE: FEED ══════ -->.*?(?=<!-- ══════ PAGE: CONFIG ══════ -->)', replace_text, content, flags=re.DOTALL)
        elif name == "config":
            content = re.sub(r'<!-- ══════ PAGE: CONFIG ══════ -->.*?(?=<!-- ══════ PAGE: CHAT \(OPEN WEBUI CLONE\) ══════ -->)', replace_text, content, flags=re.DOTALL)
        elif name == "chat":
            content = re.sub(r'<!-- ══════ PAGE: CHAT \(OPEN WEBUI CLONE\) ══════ -->.*?(?=<!-- Bottom Player -->)', replace_text + "\n</div>\n\n", content, flags=re.DOTALL)
            
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Split completed.")
