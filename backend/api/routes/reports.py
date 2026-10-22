"""Reports: list, load, save drafts, generate from operation records, submit for review."""

from __future__ import annotations


def reports(ctx):
    return {"reports": ctx.db.reports(ctx.user)}


def report(ctx):
    # GET reports/{id}; "current" may not exist yet.
    report_id = ctx.path[len("reports/"):]
    if report_id == "current" and not ctx.db.report("current"):
        return {"report": None}
    return {"report": ctx.db.load_report(ctx.user, report_id)}


def save(ctx):
    return {"report": ctx.db.save_report(ctx.user, ctx.body)}


def save_current(ctx):
    return {"report": ctx.db.save_report(ctx.user, {**ctx.body, "id": "current"})}


def generate(ctx):
    return {"report": ctx.db.generate_report(ctx.user, ctx.body)}


def submit(ctx):
    return ctx.db.submit_report(ctx.user, ctx.body)


def delete(ctx):
    return ctx.db.delete_report(ctx.user, ctx.body)


GET = {"reports": reports}
GET_PREFIX = [("reports/", report)]
POST = {"reports": save, "reports/current": save_current, "reports/generate": generate, "reports/submit": submit,
        "reports/delete": delete}
