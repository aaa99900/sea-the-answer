"""Owner-scoped conversation views over the existing, backup-covered queries."""
from psycopg.types.json import Jsonb
from ..errors import require
from ..validation import stamp


class ConversationStore:
    def lock_conversation(self, user, conversation_id):
        require(isinstance(conversation_id, str) and 0 < len(conversation_id) <= 100,
                "대화 ID를 확인해 주세요.")
        row = self.one("""SELECT q.* FROM queries q JOIN query_owner o ON o.id=q.id
            WHERE q.id=%s AND o.owner=%s FOR UPDATE OF q""", (conversation_id, user["id"]))
        require(row and row["response"].get("conversationId", row["id"]) == conversation_id,
                "대화를 찾을 수 없습니다.", "NOT_FOUND", 404)
        return row

    def attach_conversation(self, answer, conversation_id):
        answer["conversationId"] = conversation_id
        self.run("UPDATE queries SET response=%s WHERE id=%s", (Jsonb(answer), answer["id"]))

    def conversations(self, user):
        rows = self.all("""SELECT COALESCE(q.response->>'conversationId',q.id) AS id,
            min(q.created_at) AS started, max(q.created_at) AS updated, count(*) AS count,
            (array_agg(q.question ORDER BY q.created_at,q.id))[1] AS question
            FROM queries q JOIN query_owner o ON o.id=q.id WHERE o.owner=%s
            GROUP BY COALESCE(q.response->>'conversationId',q.id)
            ORDER BY max(q.created_at) DESC, id LIMIT 100""", (user["id"],))
        return [{"id": r["id"], "question": r["question"], "at": stamp(r["updated"]),
                 "count": r["count"]} for r in rows]

    def conversation(self, user, conversation_id):
        self.lock_conversation(user, conversation_id)
        rows = self.all("""SELECT q.* FROM queries q JOIN query_owner o ON o.id=q.id
            WHERE o.owner=%s AND COALESCE(q.response->>'conversationId',q.id)=%s
            ORDER BY q.created_at,q.id""", (user["id"], conversation_id))
        turns = []
        for row in rows:
            answer = row["response"]
            visible = all(self.can_read_document(user, e["document_id"]) for e in answer.get("evidence", []))
            turns.append({"id": row["id"], "question": row["question"], "at": stamp(row["created_at"]),
                          "answer": answer if visible else None, "unavailable": not visible})
        return {"id": conversation_id, "turns": turns}

    def delete_conversation(self, user, conversation_id):
        # The root row also serializes concurrent appends and deletion.
        self.lock_conversation(user, conversation_id)
        rows = self.all("""SELECT q.id FROM queries q JOIN query_owner o ON o.id=q.id
            WHERE o.owner=%s AND COALESCE(q.response->>'conversationId',q.id)=%s""",
            (user["id"], conversation_id))
        ids = [r["id"] for r in rows]
        self.run("DELETE FROM query_owner WHERE id=ANY(%s) AND owner=%s", (ids, user["id"]))
        self.run("DELETE FROM queries WHERE id=ANY(%s)", (ids,))
        self.audit(user, "query.delete", "질의", conversation_id, {"count": len(ids)})
        return {"deleted": conversation_id, "count": len(ids)}
