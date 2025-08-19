import smtplib, ssl, os, json, csv, time
from datetime import date, datetime
from getpass import getpass
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import threading

# -- konfigurejshn--

TEMPLATES_FILE = "templates.json"
COUNTER_FILE = "mail_counter.json"
LOG_FILE = "sent_log.json"
BATCH_SIZE = 3
PAUSE_SECONDS = 5
DAILY_LIMIT = 500 # gmail free limit




# --- Load templates ---
def load_templates():
    with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["templates"]

# --- Load/save counter ---
def load_counter():
    if not os.path.exists(COUNTER_FILE):
        return {}
    with open(COUNTER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_counter(counter):
    with open(COUNTER_FILE, "w", encoding="utf-8") as f:
        json.dump(counter, f, indent=4, ensure_ascii=False)

# --- Update daily counter ---
def update_counter(email, count=1):
    today = str(date.today())
    counter = load_counter()
    if today not in counter:
        counter[today] = {}
    if email not in counter[today]:
        counter[today][email] = 0
    counter[today][email] += count
    save_counter(counter)

def get_today_count(email):
    today = str(date.today())
    counter = load_counter()
    return counter.get(today, {}).get(email, 0)


def log_mail(email, subject, status):
    log_entry = {
        "email": email,
        "subject": subject,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": status
    }
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    logs.append(log_entry)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=4, ensure_ascii=False)
    

# --- Send email ---
def send_email(sender, password, receiver, subject, body, attachments=[]):
    port = 465
    smtp_server = "smtp.gmail.com"

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))  # UTF-8 support


    for file_path in attachments:
        try:
            with open(file_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(file_path)}"
            )
            msg.attach(part)
        except Exception as e:
            print(f"Greska kod privitka {file_path}: {e}")

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        update_counter(sender)
        log_mail(receiver, subject, "Poslano")
        return True
    except Exception as e:
        log_mail(receiver, subject, f"Greska: {e}")
        print(f"Greska kod slanja maila {receiver}: {e}")
        return False


def load_recipients_csv(csv_file):
    recipients = []
    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            recipients.append(row)
    return recipients


def load_recipients_json(json_file):
    with open(json_file, encoding='utf-8') as f:
        return json.load(f)
    

# -- gui--

class BHPostaGUI:
    def __init__(self, master):
        self.master = master
        master.title("BH-Posta e-sekretar")
        master.geometry("700x600")

        self.templates = load_templates()
        self.recipients = []
        self.attachments = []

        #sender info
        tk.Label(master, text="Vas gmail:").pack()
        self.entry_sender = tk.Entry(master, width=50)
        self.entry_sender.pack()
        tk.Label(master, text="App Password:").pack()
        self.entry_password = tk.Entry(master, show="*", width=50)
        self.entry_password.pack()

        # template selection
        tk.Label(master, text="Odaberite template:").pack()
        self.template_var = tk.StringVar(master)
        template_options = [f"{t['id']}. {t['subject']}" for t in self.templates] + ["Custom"]
        self.template_var.set(template_options[0])
        tk.OptionMenu(master, self.template_var, *template_options).pack()

        # custom subject/body

        tk.Label(master, text="Custom subject:").pack()
        self.entry_subject = tk.Entry(master, width=50)
        self.entry_subject.pack()
        tk.Label(master, text="Custom body:").pack()
        self.text_body = tk.Text(master, height=10, width=60)
        self.text_body.pack()

        #recipients 
        tk.Button(master, text="Ucitaj primaoce CSV", command=self.load_csv).pack(pady=2)
        tk.Button(master, text="Ucitaj primaoce JSON", command=self.load_json).pack(pady=2)
        tk.Button(master, text="Ucitaj primaoce rucno", command=self.manual_recipients).pack(pady=2)

        tk.Button(master, text="Dodaj privitke", command=self.add_attachments).pack(pady=2)

        self.status_text = tk.Text(master, height=10, width=80)
        self.status_text.pack(pady=10)

        tk.Button(master, text="Posalji mailove", command=self.start_sending).pack(pady=5)

    
    def log_status(self, message):
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.master.update()

    def load_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if file_path:
            self.recipients = load_recipients_csv(file_path)
            self.log_status(f"Ucitano {len(self.recipients)} primaoca iz CSV")

    def load_json(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if file_path:
            self.recipients = load_recipients_json(file_path)
            self.log_status(f"Ucitano {len(self.recipients)} primaoca iz JSON")

    def manual_recipients(self):
        user_input = simpledialog.askstring("Rucni unos", "Unesite primaoce (email:ime, email:ime, ...)")
        if user_input:
            recipients = []
            pairs = user_input.split(",")
            for p in pairs:
                try:
                    email, name = p.split(":")
                    recipients.append({"email": email.strip(),"name": name.strip() })
                except:
                    self.log_status(f"Neispravan unos: {p}")
            self.recipients = recipients
            self.log_status(f"Uneseno {len(self.recipients)} primaoca rucno")


    def add_attachments(self):
        files = filedialog.askopenfilenames()
        self.attachments.extend(files)
        self.log_status(f"Dodano {len(files)} privitaka")

    def start_sending(self):
        threading.Thread(target=self.send_batch).start()

    def send_batch(self):
        sender = self.entry_sender.get().strip()
        password = self.entry_password.get().strip()
        if not sender or not password:
            messagebox.showerror("Greska", "Unesite gmail i app password")
            return
        
        selected = self.template_var.get()
        if selected == "Custom":
            subject = self.entry_subject.get().strip()
            body = self.text_body.get("1.0", tk.END).strip()
        else:
            tmpl_id = int(selected.split(".")[0])
            tmpl = next((t for t in self.templates if t["id"] == tmpl_id), None)
            subject = tmpl["subject"]
            body = tmpl["body"]

        # daily limit check
        sent_today = get_today_count(sender)
        total = len(self.recipients)
        if sent_today + total > DAILY_LIMIT:
            cont = messagebox.askyesno("Upozorenje", f"Slanejem ovih mailova premasit cete limit ({DAILY_LIMIT}). Nastaviti?")
            if not cont:
                return
            
        # batch sending
        for i in range(0, total, BATCH_SIZE):
            batch = self.recipients[i:i+BATCH_SIZE]
            self.log_status(f"Slanje batch-a {i//BATCH_SIZE + 1} ({len(batch)} mailova)")
            for r in batch:
                personalized_body = body.replace("{name}", r["name"])
                success = send_email(sender, password, r["email"], subject, personalized_body, self.attachments)
                if success:
                    self.log_status(f"Poslan mail: {r['email']}")
                else:
                    self.log_status(f"Greska kod slanja: {r['email']}")
                time.sleep(PAUSE_SECONDS)
            self.log_status(f"Trenutni broj poslanih mailova danas: {get_today_count(sender)}")
        self.log_status("Batch slanje zavrseno!")
                
if __name__ == "__main__":
    root = tk.Tk()
    app = BHPostaGUI(root)
    root.mainloop()




        







# def manual_input_recipients():
#     recipients = []
#     user_input = input("Unesite primaoce (pr. email:ime, haso@gmail.com:Haso, mujo@gmail.com:Mujo, .. itd): ")
#     pairs = user_input.split(",")
#     for p in pairs:
#         email, name = p.split(":")
#         recipients.append({"email": email.strip(), "name": name.strip()})
#     return recipients



# # --- MAIN ---
# if __name__ == "__main__":
#     print(" Dobrodošli u BH-Posta e-sekretar")
#     sender = input("Unesite svoj Gmail: ")
#     password = getpass("Unesite svoj App Password: ")

#     sent_today = get_today_count(sender)
#     print(f"\nDanas je poslano: {sent_today} mailova.")

#     # --- Load templates ---
#     templates = load_templates()
#     print("\nDostupni template-i:")
#     for t in templates:
#         print(f"{t['id']}. {t['subject']}")

#     choice = input("Odaberite template (1-5) ili 'c' za custom: ")

#     if choice.lower() == "c":
#         subject = input("Unesite subject: ")
#         body = input("Unesite poruku: ")
#     else:
#         tmpl = next((t for t in templates if str(t["id"]) == choice), None)
#         if tmpl:
#             subject, body = tmpl["subject"], tmpl["body"]
#         else:
#             print(" Pogrešan izbor, prekidam operaciju.")
#             exit()

#     print("\nOpcije unosa primaoca:")
#     print("1. CSV fajl")
#     print("2. JSON fajl")
#     print("3. Rucni unos u terminal")
#     source_choice = input("Odaberite opciju (1-3): ")

#     if source_choice == "1":
#         csv_file = input("Unesite ime CSV fajla: ")
#         recipients = load_recipients_csv(csv_file)
#     elif source_choice == "2":
#         json_file = input("Unesite ime JSON fajla: ")
#         recipients = load_recipients_json(json_file)
#     elif source_choice == "3":
#         recipients = manual_input_recipients()
#     else:
#         print("Pogresan izbor, prekidam radnju.")
#         exit()
    
#     total = len(recipients)
#     print(f"\n Ukupno primaoca: {total}")


#     # provjera dnevnog limita
#     if sent_today + total > DAILY_LIMIT:
#         print(f" Upozorenje: Slanjem ovih mailova premasit cete dnevni limit ({DAILY_LIMIT}).")
#         cont = input("Zelite li nastaviti? (y/n):")
#         if cont.lower() != "y":
#             print("Prekidam slanje.")
#             exit()

#     attach_input = input("Unesite putanje fajlova za privitke, odvojene zarezom ili Enter za nista: ")
#     attachments = [f.strip() for f in attach_input.split(",") if f.strip()] if attach_input else []

#     for i in range(0, total, BATCH_SIZE):
#         batch = recipients[i:i+BATCH_SIZE]
#         print(f"\n Slanje batch-a {i//BATCH_SIZE + 1} ({len(batch)} mailova)")
#         for r in batch:
#             personalized_body = body.replace("{name}", r["name"])
#             send_email(sender, password, r["email"], subject, personalized_body)
#             print(f" Poslan mail: {r['email']}")
#             time.sleep(PAUSE_SECONDS)
#         print(f"Trenutni broj poslanih mailova danas: {get_today_count(sender)}")

#     print("\n Batch slanje zavrseno!")



    # receiver = input("Unesite email primatelja: ")
    # send_email(sender, password, receiver, subject, body)

    # print(" Mail poslan!")
    # print(" Trenutni broj poslanih mailova danas:", get_today_count(sender))
