"""Check that the browser and the server accept and reject exactly the same input.

    python scripts/parity_check.py          (needs Node 20+; exits 1 on any mismatch and prints every difference)

The React forms validate before sending (fast feedback) and the API validates again (the real protection). If the two rule sets
drift apart, users see surprises: the form accepts something the server refuses, or the form blocks something the API allows.
Each case below goes through the client's rules (client/src/utils/validation.js, run by Node) and the server's rules
(server/studysync/validation.py); the yes/no verdicts must match.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from studysync import validation as sv  # noqa: E402

ZW = "\u200b"
EMOJI = "\U0001F600"
CASES = []


def add(rule, values, **kw):
    for v in values:
        CASES.append({"rule": rule, "value": v, **kw})


add("required", ["", " ", "\t\n", "a", " a ", ZW, ZW * 5, " " + ZW + " ", "\ufeff", "\u2060x", EMOJI], label="Name")
add("minLength", ["ab", "abc", " abc ", "a" + ZW + "bc", ZW * 3, EMOJI * 3, EMOJI * 2, "\u00e9\u00e9\u00e9", "e\u0301e\u0301"], label="Title", n=3)
add("maxLength", ["a" * 60, "a" * 61, EMOJI * 60, EMOJI * 61, " " + "a" * 60 + " ", "\u00e9" * 60], label="Name", n=60)
add("singleLine", ["Alex Rao", "Alex\nRao", "Alex\x00Rao", "  Alex  ", "Alex\n", "\nAlex", "tab\tinside", "Alex\u2028Rao", "emoji " + EMOJI], label="Name")
add("email", ["a@b.co", "a@b", "a b@c.co", "@b.co", "a@@b.co", "a@b.c", " a@b.co ", "a@b.co\n", "A@B.CO", "zo\u00e9@example.com", "a" * 245 + "@b.co", "a" * 250 + "@b.co", "a@b..co", "a@b.co ", "a\u200b@b.co"])
add("password", ["abcdefg1", "abcdefgh", "12345678", "abc1234", "a1" * 64, "a1" * 64 + "x", "abcdefg\u0663", "abcdefgh\u0663", "abc12345\r", "abc12345\n", "abc 12345", EMOJI + "abc12345", "pass\u00e9word1", "a" * 7 + "1", "ABCDEFG1"])
add("url", ["https://example.com", "http://localhost:5000/x?y=1", "ftp://x.co", "javascript:alert(1)", "example.com", "https://", "HTTPS://EXAMPLE.COM", "https://exa mple.com", "http:/example.com", "http:///example.com", "https:\\\\example.com", "https://a.co/" + "a" * 2100, "https://x.co/\u00e9", "https://ex\x00ample.com", "https://user:pw@example.com/", "https://example.com/path with space", "  https://example.com  ", "data:text/html,hi", "//example.com", "https://[::1]/"])

SERVER = {
    "required": lambda c: sv.required(c["label"])(c["value"]) == "",
    "minLength": lambda c: sv.min_length(c["n"], c["label"])(c["value"]) == "",
    "maxLength": lambda c: sv.max_length(c["n"], c["label"])(c["value"]) == "",
    "singleLine": lambda c: sv.single_line(c["label"])(c["value"]) == "",
    "email": lambda c: sv.email_rule(c["value"]) == "",
    "password": lambda c: sv.password_rule(c["value"]) == "",
    "url": lambda c: sv.url_rule(c["value"]) == "",
}


def subjects_match() -> list[str]:
    """The subject list and spine colours are defined twice (client and server); they must be identical."""
    run = subprocess.run(["node", "-e", "import('./src/utils/subjects.js').then(m => console.log(JSON.stringify(m.SUBJECT_COLORS)))"], capture_output=True, text=True, cwd=ROOT / "client")
    from studysync.subjects import SUBJECT_COLORS
    client = json.loads(run.stdout)
    problems = []
    if list(client) != list(SUBJECT_COLORS):
        problems.append(f"subject lists differ: client={list(client)} server={list(SUBJECT_COLORS)}")
    for name, colour in SUBJECT_COLORS.items():
        if client.get(name) != colour:
            problems.append(f"colour for {name}: client={client.get(name)} server={colour}")
    return problems


def main():
    run = subprocess.run(["node", str(ROOT / "client" / "tests-node" / "parity-rules.mjs")], input=json.dumps(CASES), capture_output=True, text=True, cwd=ROOT / "client")
    if run.returncode != 0:
        print(run.stderr)
        return 2
    client = json.loads(run.stdout)
    mismatches = []
    for case, c_ok in zip(CASES, client):
        s_ok = SERVER[case["rule"]](case)
        if c_ok != s_ok:
            mismatches.append((case, c_ok, s_ok))
    subject_problems = subjects_match()
    print(f"{len(CASES)} validation cases, {len(mismatches)} mismatches; subjects and colours: {'identical' if not subject_problems else 'DIFFERENT'}")
    for problem in subject_problems:
        print("  " + problem)
    for case, c_ok, s_ok in mismatches:
        shown = repr(case["value"])
        shown = shown if len(shown) < 60 else shown[:57] + "..."
        print(f"  {case['rule']:10s} {shown:62s} client={'accepts' if c_ok else 'rejects'}  server={'accepts' if s_ok else 'rejects'}")
    return 1 if (mismatches or subject_problems) else 0


if __name__ == "__main__":
    sys.exit(main())
