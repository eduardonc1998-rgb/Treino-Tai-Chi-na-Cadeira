#!/usr/bin/env python3
"""Crawl the local mirror with synthetic answers and save a record per step.

Requires: pip install playwright && playwright install chromium
Start the local server first (python serve.py --site site).
"""
from __future__ import annotations
import argparse
import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlparse

AGES = ["40-49", "50-59", "60-69", "70+"]
GENDERS = [("Feminino", "female"), ("Masculino", "male")]
SYNTHETIC = {"height": "165", "weight": "68", "target_weight": "64", "age": "55", "date": "2027-05-15", "email": "capture+test@example.invalid"}

def safe_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")

async def visible_button_texts(page):
    return [s.strip() for s in await page.locator("button, [role=button], label").all_text_contents() if s.strip()]

async def click_named(page, label: str) -> bool:
    for selector in ("main button", "main [role=button]", "main label", "button", "[role=button]", "label"):
        loc = page.locator(selector).filter(has_text=re.compile(rf"^{re.escape(label)}$", re.I)).first
        try:
            if await loc.count() and await loc.is_visible():
                await loc.click(timeout=2500)
                return True
        except Exception:
            pass
    return False

async def click_continue(page) -> bool:
    pat = re.compile(r"^(continuar|continue|próximo passo|próxima|avançar|obter meu plano|ver meu plano|ok|entendi|feito)$", re.I)
    for loc in await page.get_by_role("button").all():
        try:
            txt = (await loc.inner_text()).strip()
            if pat.match(txt) and await loc.is_visible() and await loc.is_enabled():
                await loc.click(timeout=3000)
                return True
        except Exception:
            continue
    return False

async def capture(page, folder: Path, n: int, step_id: str, node: dict, branch: str):
    stem = f"{n:03d}_{step_id}"
    html = await page.content()
    try: text = await page.locator("main").inner_text(timeout=1500)
    except Exception: text = await page.locator("body").inner_text(timeout=1500)
    options = await visible_button_texts(page)
    (folder / f"{stem}.html").write_text(html, encoding="utf-8")
    (folder / f"{stem}.txt").write_text(text, encoding="utf-8")
    (folder / f"{stem}.json").write_text(json.dumps({
        "branch": branch, "step": n, "step_id": step_id, "url": page.url,
        "type": node.get("type"), "template": node.get("templateId"),
        "name": node.get("name"), "question": node.get("data", {}).get("question"),
        "title": node.get("data", {}).get("title"), "options_found": options,
        "main_text": text
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    await page.screenshot(path=str(folder / f"{stem}.png"), full_page=True)
    return text, options

async def fill_synthetic(page, node: dict):
    data = node.get("data", {})
    measurement = str(data.get("measurementType", "")).lower()
    q = str(data.get("question", "")).lower()
    if "email" in node.get("templateId", ""):
        value = SYNTHETIC["email"]
    elif "date" in node.get("templateId", "") or "data" in q or "quando será" in q:
        value = SYNTHETIC["date"]
    elif measurement == "height" or "altura" in q:
        value = SYNTHETIC["height"]
    elif measurement == "age" or "idade" in q:
        value = SYNTHETIC["age"]
    elif measurement in ("weight", "current_weight") or "peso atual" in q:
        value = SYNTHETIC["weight"]
    elif "peso ideal" in q or "peso desejado" in q:
        value = SYNTHETIC["target_weight"]
    else:
        value = "1"
    fields = page.locator("main input:visible, main textarea:visible")
    count = await fields.count()
    for i in range(count):
        field = fields.nth(i)
        typ = (await field.get_attribute("type") or "text").lower()
        if typ in ("checkbox", "radio", "button", "submit"):
            continue
        await field.fill(value)
    return value if count else None

async def run_branch(browser, base_url: str, nodes: dict, age: str, gender_label: str, out: Path, max_steps: int):
    branch = f"{age}_{'female' if gender_label == 'Feminino' else 'male'}"
    folder = out / f"capture_{safe_slug(branch)}"
    folder.mkdir(parents=True, exist_ok=True)
    context = await browser.new_context(viewport={"width": 1365, "height": 900}, device_scale_factor=1)
    page = await context.new_page()
    origin = urlparse(base_url).netloc
    requests, failed, console_errors = [], [], []
    page.on("request", lambda r: requests.append({"method": r.method, "type": r.resource_type, "url": r.url}))
    page.on("requestfailed", lambda r: failed.append({"type": r.resource_type, "url": r.url, "failure": r.failure}))
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    async def only_local(route):
        if urlparse(route.request.url).netloc == origin:
            await route.continue_()
        else:
            await route.abort()
    await page.route("**/*", only_local)
    await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
    await page.locator("main").wait_for(state="visible", timeout=20000)
    current = next(iter(nodes))
    seen = set(); record = []; status = "max_steps"

    for n in range(1, max_steps + 1):
        # SvelteKit rewrites the pathname suffix to the current next-step id.
        path_id = page.url.rstrip("/").split("/")[-1]
        step_id = path_id if path_id in nodes else current
        node = nodes[step_id]
        if step_id in seen:
            status = "cycle_or_revisit"; break
        seen.add(step_id)
        text, options_found = await capture(page, folder, n, step_id, node, branch)
        record.append({"step_id": step_id, "type": node.get("type"), "template": node.get("templateId"), "text": text[:400]})
        if node.get("type") == "summary":
            status = "stopped_before_purchase"; break

        if step_id == next(iter(nodes)):
            action_label = age
            acted = await click_named(page, action_label)
        elif node.get("name") == "Image Cards" and node.get("data", {}).get("question", "").lower().find("gênero") >= 0:
            action_label = gender_label
            acted = await click_named(page, action_label)
        elif node.get("templateId") == "multi-selection-default":
            opts = node.get("data", {}).get("options", []) or []
            action_label = str(opts[0].get("label", "")) if opts else ""
            acted = await click_named(page, action_label) if action_label else False
            if acted and page.url.endswith(step_id):
                acted = await click_continue(page)
        elif node.get("templateId", "").startswith("input-") or node.get("type") == "email_capture":
            await fill_synthetic(page, node)
            acted = await click_continue(page)
        elif node.get("type") == "results" and node.get("templateId") == "analyze-loading":
            before = page.url
            try: await page.wait_for_function("u => location.href !== u", arg=before, timeout=15000)
            except Exception: pass
            acted = page.url != before
        else:
            opts = node.get("data", {}).get("options", []) or []
            action_label = str(opts[0].get("label", "")) if opts else ""
            acted = await click_named(page, action_label) if action_label else await click_continue(page)

        if not acted:
            status = "blocked_at_step"
            break
        before = step_id
        try:
            await page.wait_for_function("arg => location.pathname.split('/').filter(Boolean).slice(-1)[0] !== arg", arg=before, timeout=5000)
        except Exception:
            await page.wait_for_timeout(400)
        path_id = page.url.rstrip("/").split("/")[-1]
        if path_id not in nodes:
            # Some SvelteKit steps retain the route; use the first unmatched outgoing edge.
            targets = [e.get("targetStepId") for e in node.get("connections", []) if e.get("targetStepId") in nodes]
            path_id = targets[0] if targets else ""
        if path_id in nodes: current = path_id
        else:
            status = "unknown_next_route"; break

    (folder / "run.json").write_text(json.dumps({"branch":branch,"age":age,"gender":gender_label,"status":status,"captured_steps":record,"requests":requests,"failed_requests":failed,"console_errors":console_errors},ensure_ascii=False,indent=2),encoding="utf-8")
    await context.close()
    return {"branch": branch, "status": status, "steps": len(record), "first_purchase_captured": any((out/f"capture_{safe_slug(branch)}").glob("*summary*.png")), "failed_requests": len(failed), "console_errors": len(console_errors)}

async def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url",default="http://127.0.0.1:8000/pt/flow-tai-chi-yoga-2")
    ap.add_argument("--site",default="site")
    ap.add_argument("--out",default=".")
    ap.add_argument("--max-steps",type=int,default=70)
    ap.add_argument("--age",action="append",choices=AGES)
    ap.add_argument("--gender",action="append",choices=[g[0] for g in GENDERS])
    args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    funnel=json.loads((Path(args.site)/".."/"funnel_graph.json").resolve().read_text(encoding="utf-8"))
    nodes={s["id"]:s for s in funnel["steps"]}
    if not nodes: raise SystemExit("No funnel steps found in funnel_graph.json")
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise SystemExit("Install Playwright first: python -m pip install playwright; python -m playwright install chromium") from e
    ages=args.age or AGES; genders=args.gender or [g[0] for g in GENDERS]
    results=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        for age in ages:
            for gender in genders:
                results.append(await run_branch(browser,args.url,nodes,age,gender,out,args.max_steps))
        await browser.close()
    (out/"branch_matrix.json").write_text(json.dumps({"source_url":args.url,"funnel_id":funnel["id"],"step_nodes":len(nodes),"synthetic_values":SYNTHETIC,"results":results},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(results,ensure_ascii=False,indent=2))

if __name__=="__main__": asyncio.run(main())
