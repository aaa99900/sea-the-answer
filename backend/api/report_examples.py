"""Install shared, read-only report examples once under the bootstrap transaction lock."""
import json

from psycopg.types.json import Jsonb

MARKER = 'report-examples:five-forms-v1'


def retire_default_noon_reports(store, samples):
    # Old generators used random IDs. Require the original three-ship set,
    # the actual fixture record, and an identical, unedited generated report.
    ships = {s['id'] for s in samples['ships']}
    records = {(r['ship'], r['date']): r for r in samples['records']}
    matches = []
    for row in store.all("""SELECT r.id FROM reports r JOIN report_meta m USING(id)
            WHERE r.version=1 AND m.status='draft' AND m.body->>'template'='noon'
            AND m.body->>'sample'='true' AND NOT EXISTS (
                SELECT 1 FROM changes WHERE kind='report.approve' AND payload->>'id'=r.id)
            FOR UPDATE OF r,m"""):
        report = store.report(row['id'])
        body = report['body']
        ship, day = body.get('ship'), body.get('from')
        fixture = records.get((ship, day))
        if not fixture or day != body.get('to') or not store.one('SELECT 1 FROM ships WHERE id=%s',(ship,)):
            continue
        summary = store.operation_summary({'ship':ship, 'from':day, 'to':day})
        rows = summary['rows']
        if len(rows) != 1 or not rows[0].get('sample') or rows[0].get('version') != 1:
            continue
        if any(rows[0].get(k) != fixture[k] for k in ('id','ship','date','fuel','distance','speed')):
            continue
        original = store.generated_report_payload(summary, 'noon')
        if all(report[k] == original[k] for k in ('title','type','text','body','sources')):
            matches.append((ship,row['id']))
    if len(matches) == len(ships) and {ship for ship,_ in matches} == ships:
        ids = [identifier for _,identifier in matches]
        # Archive identifiable system-generated examples; keep their stored originals.
        store.run("UPDATE report_meta SET status='retired_example' WHERE id=ANY(%s)", (ids,))


def install_report_examples(store, knowledge):
    if store.one('SELECT 1 FROM settings WHERE key=%s', (MARKER,)):
        return
    retire_default_noon_reports(store, json.loads((knowledge/'sample-data.json').read_text(encoding='utf-8')))
    for example in json.loads((knowledge/'report-examples.json').read_text(encoding='utf-8')):
        inserted = store.one("""INSERT INTO reports (id,title,type,text,sources,version,updated_at)
            VALUES (%s,%s,%s,%s,'[]',1,now()) ON CONFLICT(id) DO NOTHING RETURNING id""",
            (example['id'],example['title'],example['type'],example['text']))
        if inserted:
            store.run("INSERT INTO report_meta VALUES (%s,%s,'example',%s)",
                      (example['id'],'system-report-examples',Jsonb(example['body'])))
    store.run('INSERT INTO settings(key,value) VALUES(%s,%s)',(MARKER,'installed'))
