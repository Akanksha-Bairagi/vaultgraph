import { useState, type FormEvent } from "react";
import { Loader2, Pencil, Plus, ShieldAlert, Users } from "lucide-react";
import { useAuth } from "../auth.tsx";
import { messageOf, useAsync } from "../hooks.ts";
import { api } from "../lib/client.ts";
import type { UserItem } from "../types.ts";
import { Badge, Card, Empty, ErrorNote, GroupPicker, Modal, PageHeader, Spinner } from "../components/ui.tsx";

export function People() {
  const { user } = useAuth();
  const users = useAsync(() => api.users(), []);
  const groups = useAsync(() => api.groups(), []);
  const [editing, setEditing] = useState<UserItem | null>(null);
  const [gname, setGname] = useState("");
  const [gerr, setGerr] = useState<string | null>(null);
  const [nu, setNu] = useState({ email: "", password: "", role: "member", groups: [] as string[] });
  const [uerr, setUerr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const names = (groups.data ?? []).map((g) => g.name);

  if (user?.role !== "admin") return <Card><Empty icon={<ShieldAlert size={26} />} title="Administrator access required" hint="Only workspace administrators can manage people and groups." /></Card>;

  async function addGroup(e: FormEvent) {
    e.preventDefault(); setGerr(null);
    try { await api.createGroup(gname.trim()); setGname(""); groups.reload(); } catch (err) { setGerr(messageOf(err)); }
  }
  async function addUser(e: FormEvent) {
    e.preventDefault(); setUerr(null); setBusy(true);
    try { await api.createUser(nu.email.trim(), nu.password, nu.groups, nu.role); setNu({ email: "", password: "", role: "member", groups: [] }); users.reload(); groups.reload(); }
    catch (err) { setUerr(messageOf(err)); } finally { setBusy(false); }
  }

  return (
    <>
      <PageHeader title="People & groups" subtitle="Group membership decides which documents each person can search. Changes take effect immediately." />
      <div className="two-col wide-left">
        <Card title="People">
          {users.error && <ErrorNote message={users.error} onRetry={users.reload} />}
          {users.loading && !users.data && <Spinner />}
          {users.data && users.data.length === 0 && <Empty icon={<Users size={24} />} title="No people yet" />}
          <ul className="list">
            {users.data?.map((u) => (
              <li key={u.id} className="list-row">
                <div>
                  <strong>{u.email}</strong>
                  <div className="chips">{u.role === "admin" && <Badge tone="info">admin</Badge>}{u.groups.length ? u.groups.map((g) => <span key={g} className="chip">{g}</span>) : <span className="muted small">no groups</span>}</div>
                </div>
                <button className="btn btn-sm" onClick={() => setEditing(u)}><Pencil size={13} /> Edit groups</button>
              </li>
            ))}
          </ul>
        </Card>

        <div className="stack">
          <Card title="Groups">
            <ul className="chips spaced">{groups.data?.map((g) => <li key={g.id} className="chip chip-lg">{g.name}<span className="count">{g.members ?? 0}</span></li>)}</ul>
            {groups.data?.length === 0 && <p className="muted small">Create a group to start sharing documents.</p>}
            <form className="inline-form" onSubmit={addGroup}>
              <input value={gname} onChange={(e) => setGname(e.target.value)} placeholder="new-group-name" pattern="[A-Za-z0-9_\-]{1,50}" title="Letters, digits, _ and - only" required aria-label="New group name" />
              <button className="btn"><Plus size={15} /> Add</button>
            </form>
            {gerr && <ErrorNote message={gerr} />}
          </Card>

          <Card title="Add a person">
            <form className="form" onSubmit={addUser}>
              <label>Email<input type="email" required value={nu.email} onChange={(e) => setNu({ ...nu, email: e.target.value })} /></label>
              <label>Temporary password<input type="password" required minLength={10} value={nu.password} onChange={(e) => setNu({ ...nu, password: e.target.value })} placeholder="At least 10 characters" autoComplete="new-password" /></label>
              <label>Role<select value={nu.role} onChange={(e) => setNu({ ...nu, role: e.target.value })}><option value="member">Member</option><option value="admin">Administrator</option></select></label>
              <div><span className="label">Groups</span><GroupPicker groups={names} selected={nu.groups} onChange={(g) => setNu({ ...nu, groups: g })} /></div>
              {uerr && <ErrorNote message={uerr} />}
              <button className="btn btn-primary" disabled={busy}>{busy ? <Loader2 size={16} className="spin" /> : <Plus size={16} />} Create person</button>
            </form>
          </Card>
        </div>
      </div>

      {editing && <EditGroups u={editing} names={names} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); users.reload(); groups.reload(); }} />}
    </>
  );
}

function EditGroups({ u, names, onClose, onSaved }: { u: UserItem; names: string[]; onClose: () => void; onSaved: () => void }) {
  const [sel, setSel] = useState(u.groups);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function save() {
    setBusy(true); setErr(null);
    try { await api.setUserGroups(u.id, sel); onSaved(); } catch (e) { setErr(messageOf(e)); setBusy(false); }
  }
  return (
    <Modal title={`Groups for ${u.email}`} onClose={onClose}>
      <p className="muted small">Documents shared with any selected group become searchable by this person right away; removed groups stop working immediately.</p>
      <GroupPicker groups={names} selected={sel} onChange={setSel} />
      {err && <ErrorNote message={err} />}
      <div className="modal-actions"><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? <Loader2 size={16} className="spin" /> : null} Save</button></div>
    </Modal>
  );
}
