import os, io, re, hmac
from datetime import datetime, date, timedelta
from functools import wraps
from zoneinfo import ZoneInfo
from flask import Flask, request, session, redirect, jsonify, send_file, render_template_string
from flask_sqlalchemy import SQLAlchemy
from PIL import Image, ImageDraw, ImageFont
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-change-me")
db_url = os.environ.get("DATABASE_URL", "sqlite:///orders.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
db = SQLAlchemy(app)
IST = ZoneInfo("Asia/Kolkata")
def now(): return datetime.now(IST).replace(tzinfo=None)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=now, index=True)
    name = db.Column(db.String(80))
    phone = db.Column(db.String(15))
    note = db.Column(db.String(300))
    items = db.Column(db.Text)
    total = db.Column(db.Integer)
    status = db.Column(db.String(20), default="New")

with app.app_context():
    db.create_all()

def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("admin"):
            return redirect("/admin/login")
        return f(*a, **k)
    return w

@app.get("/")
def index():
    return send_file("index.html")

@app.after_request
def cors(r):
    if request.path.startswith("/api/"):
        r.headers["Access-Control-Allow-Origin"] = "*"
        r.headers["Access-Control-Allow-Headers"] = "Content-Type"
        r.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return r

@app.errorhandler(500)
def err500(e):
    if request.path.startswith("/api/"):
        return jsonify(error="Server error. Please try again in a moment."), 500
    return "Server error", 500

@app.get("/cakes")
def cakes():
    return send_file("cakes.html")

@app.route("/api/order", methods=["POST", "OPTIONS"])
def api_order():
    if request.method == "OPTIONS":
        return "", 204
    d = request.get_json(silent=True) or {}
    name = str(d.get("name", "")).strip()[:80]
    phone = "".join(c for c in str(d.get("phone", "")) if c.isdigit())[-10:]
    if not name or len(phone) != 10:
        return jsonify(error="Please enter your name and a 10-digit phone number."), 400
    lines, total = [], 0
    for it in (d.get("items") or [])[:50]:
        try:
            q = max(1, min(int(it["qty"]), 50)); p = max(0, int(it["price"]))
        except (KeyError, TypeError, ValueError):
            continue
        nm = str(it.get("name", "")).replace("\n", " ")[:60]
        lines.append(f"{nm} x{q} @{p}"); total += p * q
    if not lines:
        return jsonify(error="Your order is empty."), 400
    o = Order(name=name, phone=phone, note=str(d.get("note", ""))[:300], items="\n".join(lines), total=total)
    db.session.add(o); db.session.commit()
    return jsonify(ok=True, id=o.id)

@app.route("/admin/login", methods=["GET", "POST"])
def login():
    err = None
    if request.method == "POST":
        pw = os.environ.get("ADMIN_PASSWORD")
        user = os.environ.get("ADMIN_USER", "admin")
        ok = bool(pw) and hmac.compare_digest(request.form.get("u", "").encode(), user.encode()) \
            and hmac.compare_digest(request.form.get("p", "").encode(), pw.encode())
        if ok:
            session["admin"] = True
            return redirect("/admin")
        err = "Wrong username or password." if pw else "Set ADMIN_PASSWORD on the server first."
    return render_template_string(LOGIN, err=err)

@app.get("/admin/logout")
def logout():
    session.clear()
    return redirect("/admin/login")

@app.get("/admin")
@login_required
def admin():
    try: day = date.fromisoformat(request.args.get("date", ""))
    except ValueError: day = now().date()
    start = datetime.combine(day, datetime.min.time())
    rows = Order.query.filter(Order.created >= start, Order.created < start + timedelta(days=1)) \
        .order_by(Order.created.desc()).all()
    total = sum(o.total for o in rows if o.status != "Cancelled")
    new = sum(1 for o in rows if o.status == "New")
    return render_template_string(ADMIN, rows=rows, day=day.isoformat(), total=total, new=new)

@app.post("/admin/status/<int:oid>")
@login_required
def status(oid):
    o = db.session.get(Order, oid)
    if o and request.form.get("s") in ("New", "Preparing", "Done", "Cancelled"):
        o.status = request.form["s"]; db.session.commit()
    return redirect("/admin?date=" + request.form.get("day", ""))

@app.get("/admin/export")
@login_required
def export():
    q = Order.query.order_by(Order.created)
    label = "all-days-till-" + now().strftime("%d-%m-%Y")
    if request.args.get("date"):
        try:
            day = date.fromisoformat(request.args["date"])
            start = datetime.combine(day, datetime.min.time())
            q = q.filter(Order.created >= start, Order.created < start + timedelta(days=1))
            label = day.strftime("%d-%m-%Y")
        except ValueError:
            pass
    wb = Workbook(); ws = wb.active; ws.title = "All Orders"
    ws.append(["Order #", "Date", "Time", "Name", "Phone", "Items", "Total (Rs)", "Status", "Note"])
    days = {}
    for o in q.all():
        dk = o.created.strftime("%d-%m-%Y")
        ws.append([o.id, dk, o.created.strftime("%I:%M %p"), o.name, str(o.phone), o.items.replace("\n", "; "),
                   o.total, o.status, o.note or ""])
        if o.status != "Cancelled":
            c = days.setdefault(dk, [0, 0]); c[0] += 1; c[1] += o.total
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="4A2214")
    for col, w in zip("ABCDEFGHI", (9, 12, 10, 20, 14, 60, 11, 12, 30)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    s = wb.create_sheet("Daily Summary")
    s.append(["Date", "Orders", "Revenue (Rs)"])
    for k, v in days.items(): s.append([k, *v])
    s.append(["TOTAL", sum(v[0] for v in days.values()), sum(v[1] for v in days.values())])
    for c in s[1]: c.font = Font(bold=True)
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=f"cybers-orders-{label}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
def font(sz, bold=False, serif=False):
    n = "DejaVuSerif-Bold.ttf" if serif else "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try: return ImageFont.truetype(os.path.join(FD, n), sz)
    except OSError: return ImageFont.load_default(sz)

def parse_items(o):
    out = []
    for ln in (o.items or "").split("\n"):
        m = re.match(r"^(.*) x(\d+)(?: @(\d+))?$", ln)
        out.append((m[1], int(m[2]), int(m[3]) if m[3] else None) if m else (ln, 1, None))
    return out

@app.get("/admin/bill/<int:oid>.png")
@login_required
def bill(oid):
    o = db.session.get(Order, oid)
    if not o: return "Not found", 404
    items = parse_items(o)
    W, H = 800, 270 + 150 + 62 * len(items) + 330
    BR, GO, CR, MU = "#2a1409", "#e8b73a", "#fbf1dc", "#7a5a45"
    im = Image.new("RGB", (W, H), CR); d = ImageDraw.Draw(im)
    def ctext(y, t, f, fill):
        d.text(((W - d.textlength(t, font=f)) / 2, y), t, font=f, fill=fill)
    def rtext(x, y, t, f, fill=BR):
        d.text((x - d.textlength(t, font=f), y), t, font=f, fill=fill)
    def dash(y):
        for x in range(40, W - 40, 16): d.line((x, y, x + 8, y), fill=MU, width=2)
    d.rectangle((0, 0, W, 230), fill=BR)
    ctext(28, "Cyber’s", font(84, serif=True), GO)
    ctext(138, "Tea Point  ·  A little sweetness in life…", font(24), CR)
    ctext(182, "Call 9007 583 583", font(22, True), GO)
    y = 262
    d.text((40, y), "BILL", font=font(30, True), fill=BR)
    rtext(W - 40, y, f"No. CTP-{o.id:04d}", font(26, True))
    d.text((40, y + 48), o.name, font=font(26), fill=BR)
    rtext(W - 40, y + 48, o.created.strftime("%d-%m-%Y  %I:%M %p"), font(24), MU)
    d.text((40, y + 86), "Phone: +91 " + (o.phone or ""), font=font(24), fill=MU)
    y += 140; dash(y)
    hf = font(22, True); y += 14
    d.text((40, y), "ITEM", font=hf, fill=MU)
    rtext(520, y, "QTY", hf, MU); rtext(640, y, "RATE", hf, MU); rtext(W - 40, y, "AMOUNT", hf, MU)
    y += 44; dash(y); y += 16
    f = font(25)
    for name, q, p in items:
        while d.textlength(name, font=f) > 400 and len(name) > 4: name = name[:-2]
        d.text((40, y), name, font=f, fill=BR)
        rtext(520, y, str(q), f)
        if p is not None:
            rtext(640, y, f"₹{p}", f); rtext(W - 40, y, f"₹{p * q}", f)
        y += 62
    dash(y); y += 24
    d.text((40, y), "TOTAL", font=font(40, True), fill=BR)
    rtext(W - 40, y - 2, f"₹{o.total}", font(46, True, True), "#8b1a1a")
    y += 110
    ctext(y, "Thank you for ordering!", font(34, serif=True), BR)
    ctext(y + 56, "Eat  ·  Drink  ·  Celebrate", font(26), MU)
    ctext(y + 104, "Cyber’s Tea Point", font(22, True), GO)
    buf = io.BytesIO(); im.save(buf, "PNG"); buf.seek(0)
    return send_file(buf, mimetype="image/png", as_attachment=bool(request.args.get("dl")),
                     download_name=f"cybers-bill-{o.id:04d}.png")

BASE = """<meta name=viewport content="width=device-width,initial-scale=1"><style>
:root{color-scheme:dark}body{margin:0;background:#1d0e08;color:#fbf1dc;font-family:system-ui,sans-serif}
a{color:#e8b73a}input,select,button{font:inherit;color:inherit;background:#35190d;border:1px solid #5a3320;border-radius:10px;padding:10px}
"""
LOGIN = """<!doctype html><title>Admin login</title>""" + BASE + """
body{min-height:100vh;display:grid;place-items:center}form{background:#2a1409;border:1px solid #5a3320;border-radius:18px;padding:28px;width:min(340px,90vw)}
h1{margin:0 0 16px;font-size:22px;color:#e8b73a}input,button{width:100%;margin-bottom:10px}button{background:#e8b73a;color:#2a1409;font-weight:700;border:0;cursor:pointer}p{color:#f08a8a;margin:0 0 10px}</style>
<form method=post><h1>Cyber’s Admin</h1>{% if err %}<p>{{err}}</p>{% endif %}
<input name=u placeholder=Username autocomplete=username required><input name=p type=password placeholder=Password autocomplete=current-password required><button>Log in</button></form>"""
ADMIN = """<!doctype html><title>Orders · Cyber’s</title>""" + BASE + """
.top,.bar,.cards{display:flex;gap:12px;flex-wrap:wrap;align-items:center;padding:14px 20px}.top{justify-content:space-between;border-bottom:1px solid #5a3320}
h1{margin:0;font-size:20px;color:#e8b73a}.b{background:#e8b73a;color:#2a1409!important;font-weight:700;text-decoration:none;padding:10px 16px;border-radius:99px}.b.g{background:#fbf1dc}
.cards div{background:#2a1409;border:1px solid #5a3320;border-radius:14px;padding:12px 22px;color:#c9ad92}.cards b{display:block;font-size:26px;color:#e8b73a}
.tw{overflow-x:auto;padding:0 20px 40px}table{border-collapse:collapse;width:100%;min-width:760px}th,td{text-align:left;padding:10px;border-bottom:1px solid #5a3320;vertical-align:top}
th{color:#c9ad92;font-size:13px}td.i{white-space:pre-line}.b2{cursor:pointer;border:0;padding:8px 16px}dialog{background:#2a1409;color:inherit;border:1px solid #5a3320;border-radius:16px;width:min(520px,94vw);padding:16px}dialog::backdrop{background:#000a}dialog img{width:100%;border-radius:10px;display:block}.act{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}small{color:#c9ad92}.e{padding:40px;text-align:center;color:#c9ad92}</style>
<div class=top><h1>Cyber’s Tea Point · Orders</h1><a href=/admin/logout>Log out</a></div>
<form class=bar method=get><input type=date name=date value="{{day}}" onchange="this.form.submit()">
<a class=b href="/admin/export?date={{day}}">Download this day (Excel)</a><a class="b g" href="/admin/export">Download all days (Excel)</a></form>
<div class=cards><div><b>{{rows|length}}</b>orders</div><div><b>₹{{total}}</b>revenue</div><div><b>{{new}}</b>new</div></div>
<div class=tw>{% if rows %}<table><tr><th>#<th>Time<th>Name<th>Phone<th>Items<th>Total<th>Status<th>Bill</tr>
{% for o in rows %}<tr><td>{{o.id}}<td>{{o.created.strftime('%I:%M %p')}}<td>{{o.name}}<td><a href="tel:{{o.phone}}">{{o.phone}}</a>
<td class=i>{{o.items}}{% if o.note %}<br><small>Note: {{o.note}}</small>{% endif %}<td>₹{{o.total}}
<td><form method=post action="/admin/status/{{o.id}}"><input type=hidden name=day value="{{day}}"><select name=s onchange="this.form.submit()">
{% for s in ['New','Preparing','Done','Cancelled'] %}<option {{'selected' if s==o.status}}>{{s}}</option>{% endfor %}</select></form><td><button class="b b2" data-id="{{o.id}}" data-ph="{{o.phone}}" onclick="bill(this)">Bill</button></tr>{% endfor %}</table>
{% else %}<p class=e>No orders on this date yet.</p>{% endif %}</div>
<dialog id=dlg><img id=bimg alt="Bill"><div class=act><a class=b id=dl href=#>Download image</a><button class="b b2 g" id=wa>Send on WhatsApp</button><button id=cl>Close</button></div><p id=msg></p></dialog>
<script>
const $=i=>document.getElementById(i);let cur=null;
function bill(b){cur={id:b.dataset.id,ph:b.dataset.ph};const u="/admin/bill/"+cur.id+".png";$("bimg").src=u+"?t="+Date.now();$("dl").href=u+"?dl=1";$("msg").textContent="";$("dlg").showModal()}
$("cl").onclick=()=>$("dlg").close();
$("wa").onclick=async()=>{
 const u="/admin/bill/"+cur.id+".png",chat="https://wa.me/91"+cur.ph+"?text="+encodeURIComponent("Thank you for ordering at Cyber’s Tea Point! Here is your bill.");
 try{
  const bl=await (await fetch(u)).blob(),f=new File([bl],"cybers-bill-"+cur.id+".png",{type:"image/png"});
  if(navigator.canShare&&navigator.canShare({files:[f]})&&/Android|iPhone|iPad/i.test(navigator.userAgent)){await navigator.share({files:[f]});return}
  try{await navigator.clipboard.write([new ClipboardItem({"image/png":bl})]);$("msg").textContent="Bill image copied. Paste it in the WhatsApp chat (Ctrl+V) and send."}catch(e){$("msg").textContent="Tap Download image, then attach it in the WhatsApp chat."}
  if(!window.open(chat,"_blank"))$("msg").innerHTML+=' <a href="'+chat+'" target=_blank>Open chat</a>';
 }catch(e){if(e.name!=="AbortError")$("msg").textContent="Could not share. Use Download image."}
};
setTimeout(()=>{if(!$("dlg").open&&!document.activeElement.matches('select,input'))location.reload()},30000)</script>"""

if __name__ == "__main__":
    app.run(debug=True)
