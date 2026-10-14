"""Demo data: collectors, customer accounts and collections call transcripts dated relative to today."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CallLog, Collector, Customer
from app.services.analyzer import RuleBasedAnalyzer
from app.services.call_service import apply_analysis

COLLECTORS = [
    ("Priya Sharma", "priya.sharma@abc-demo.com", "North America - East"),
    ("Daniel Brooks", "daniel.brooks@abc-demo.com", "North America - Central"),
    ("Aisha Khan", "aisha.khan@abc-demo.com", "North America - West"),
]

# (collector_idx, account, contact, company, phone, alt_phone, email, address, shipping, home, office,
#  status, ar_balance, overdue, dpd, risk)
CUSTOMERS = [
    (0, "ABC-100231", "Michael Turner", "Turner Industrial Supply", "+1 (212) 555-0147", "+1 (212) 555-0190",
     "m.turner@turnerindustrial.com", "410 Lexington Ave, New York, NY 10017", "Dock 4, 88 Harbor Rd, Newark, NJ 07114",
     "27 Maple Ct, Hoboken, NJ 07030", "410 Lexington Ave, Floor 12, New York, NY 10017", "Promise to Pay", 48250.00, 18400.00, 42, "Medium"),
    (0, "ABC-100458", "Sarah Mitchell", "Brightline Medical Devices", "+1 (617) 555-0123", "+1 (617) 555-0177",
     "smitchell@brightlinemed.com", "1 Kendall Sq, Cambridge, MA 02139", "Receiving, 55 Commerce Way, Woburn, MA 01801",
     "14 Elm St, Somerville, MA 02143", "1 Kendall Sq, Suite 300, Cambridge, MA 02139", "In Dispute", 72900.00, 31250.00, 67, "High"),
    (0, "ABC-100672", "Robert Chen", "Chen & Partners Electronics", "+1 (215) 555-0162", None,
     "robert@chenpartners.com", "1500 Market St, Philadelphia, PA 19102", "1500 Market St, Philadelphia, PA 19102",
     "9 Spruce Ln, Cherry Hill, NJ 08002", "1500 Market St, Suite 2200, Philadelphia, PA 19102", "Active", 12600.00, 0.00, 0, "Low"),
    (0, "ABC-100889", "Linda Alvarez", "Coastal Apparel Co.", "+1 (305) 555-0184", "+1 (305) 555-0101",
     "linda.alvarez@coastalapparel.com", "200 S Biscayne Blvd, Miami, FL 33131", "Warehouse B, 7800 NW 25th St, Doral, FL 33122",
     "501 Brickell Key Dr, Miami, FL 33131", "200 S Biscayne Blvd, Floor 9, Miami, FL 33131", "Past Due", 35400.00, 22100.00, 95, "High"),
    (1, "ABC-200114", "James Patel", "Midwest Auto Parts", "+1 (312) 555-0139", "+1 (312) 555-0156",
     "jpatel@midwestautoparts.com", "233 S Wacker Dr, Chicago, IL 60606", "4500 W Ann Lurie Pl, Chicago, IL 60632",
     "88 Oak Park Ave, Oak Park, IL 60302", "233 S Wacker Dr, Suite 4100, Chicago, IL 60606", "Promise to Pay", 54800.00, 15600.00, 35, "Medium"),
    (1, "ABC-200367", "Emily Johnson", "Prairie Organics", "+1 (612) 555-0118", None,
     "emily@prairieorganics.com", "80 S 8th St, Minneapolis, MN 55402", "Loading Bay 2, 1200 Industrial Blvd, St Paul, MN 55114",
     "62 Lake St, Minneapolis, MN 55408", "80 S 8th St, Floor 5, Minneapolis, MN 55402", "Active", 8900.00, 2300.00, 12, "Low"),
    (1, "ABC-200590", "William Garcia", "Lone Star Building Materials", "+1 (214) 555-0175", "+1 (214) 555-0199",
     "wgarcia@lonestarbm.com", "2100 Ross Ave, Dallas, TX 75201", "Yard 3, 9400 Ambassador Row, Dallas, TX 75247",
     "17 Bluebonnet Trl, Plano, TX 75023", "2100 Ross Ave, Suite 800, Dallas, TX 75201", "Collections Hold", 91300.00, 64700.00, 128, "High"),
    (1, "ABC-200743", "Olivia Martinez", "Gateway Pharma Distribution", "+1 (314) 555-0133", "+1 (314) 555-0144",
     "o.martinez@gatewaypharma.com", "1 Metropolitan Sq, St. Louis, MO 63102", "Cold Chain Dock, 300 Gateway Dr, St. Louis, MO 63110",
     "45 Pershing Pl, St. Louis, MO 63112", "1 Metropolitan Sq, Floor 20, St. Louis, MO 63102", "Active", 27650.00, 4100.00, 18, "Low"),
    (2, "ABC-300208", "David Kim", "Pacific Tech Components", "+1 (408) 555-0166", "+1 (408) 555-0121",
     "dkim@pacifictech.com", "3000 Tasman Dr, Santa Clara, CA 95054", "Shipping, 3010 Tasman Dr, Santa Clara, CA 95054",
     "780 Willow Glen Way, San Jose, CA 95125", "3000 Tasman Dr, Building 2, Santa Clara, CA 95054", "Past Due", 63200.00, 28900.00, 58, "Medium"),
    (2, "ABC-300451", "Jessica Nguyen", "Evergreen Home Goods", "+1 (206) 555-0158", None,
     "jessica.nguyen@evergreenhome.com", "1201 3rd Ave, Seattle, WA 98101", "DC 1, 2200 S 216th St, Kent, WA 98032",
     "3301 Fremont Ave N, Seattle, WA 98103", "1201 3rd Ave, Suite 1500, Seattle, WA 98101", "Active", 19800.00, 0.00, 0, "Low"),
    (2, "ABC-300692", "Christopher Lee", "Desert Sun Solar", "+1 (602) 555-0187", "+1 (602) 555-0112",
     "clee@desertsunsolar.com", "2 N Central Ave, Phoenix, AZ 85004", "Warehouse 7, 4400 E Broadway Rd, Phoenix, AZ 85040",
     "1120 E Camelback Rd, Phoenix, AZ 85014", "2 N Central Ave, Suite 1100, Phoenix, AZ 85004", "In Dispute", 44750.00, 19900.00, 49, "High"),
    (2, "ABC-300915", "Amanda Wright", "Rocky Mountain Outfitters", "+1 (303) 555-0141", "+1 (303) 555-0108",
     "awright@rmoutfitters.com", "1700 Lincoln St, Denver, CO 80203", "Dock 1, 5200 Smith Rd, Denver, CO 80216",
     "640 Pearl St, Boulder, CO 80302", "1700 Lincoln St, Floor 14, Denver, CO 80203", "Promise to Pay", 31100.00, 9800.00, 28, "Medium"),
]

T_PROMISE = """Collector: Good morning, this is {collector} calling from ABC Accounts Receivable. Am I speaking with {contact}?
Customer: Yes, this is {contact}.
Collector: Thanks. I'm calling about invoice #{inv1} for $9,200.00 and invoice #{inv2} for $9,200.00, both now past due.
Customer: Right, I saw the reminder. Sorry, our AP team was short-staffed last month.
Collector: I understand. Are you able to arrange payment for the overdue balance of $18,400.00?
Customer: I can pay $9,200.00 by Friday via ACH, and the second invoice by the end of the month.
Collector: That works. I'll note a promise to pay $9,200.00 by Friday and the remaining balance by month end.
Customer: Sounds good, thanks for being flexible.
Collector: Thank you. I'll send a confirmation email with remittance details."""

T_DISPUTE = """Collector: Hi, this is {collector} with ABC Accounts Receivable. Is this {contact}?
Customer: Yes. If this is about the October invoices, I'm honestly frustrated.
Collector: I'm calling about invoice #{inv1}, which is now 60 days past due.
Customer: We were overcharged on that invoice. There's a residential delivery surcharge on shipments that went to our warehouse, and two packages were damaged.
Customer: We are not paying until that is corrected. This is the second time this has happened, it's unacceptable.
Collector: I'm sorry about that. I can open a dispute for the surcharges and the damaged shipments. Can you send the tracking numbers?
Customer: I'll email them today. I also want a supervisor to review the account.
Collector: Understood, I'll escalate to my manager and the disputes team, and call you back once I have an update."""

T_HARDSHIP = """Collector: Hello, this is {collector} from ABC collections, calling for {contact}.
Customer: Speaking.
Collector: Your account has $22,100.00 past due across several invoices, the oldest is invoice #{inv1}.
Customer: Look, cash flow has been really tight. We lost a major retail client and we're struggling.
Collector: I'm sorry to hear that. Could we set up a payment plan?
Customer: Maybe. I'll try to pay $5,000 next week, but I can't promise more than that right now.
Collector: Okay. I'll note that and send over payment plan options. Can I call you back Thursday to confirm?
Customer: Fine, call me back Thursday."""

T_PAID = """Collector: Hi {contact}, this is {collector} from ABC Accounts Receivable, following up on invoice #{inv1}.
Customer: Oh, we already paid that. The payment went out by wire on Monday.
Collector: Thank you. Do you have the reference number so I can trace it?
Customer: Sure, the wire reference is WR-558213. Should be about $2,300.00.
Collector: Perfect, I'll ask our cash application team to match it.
Customer: Great, thanks for checking. Appreciate it."""

T_CHURN = """Collector: Good afternoon, this is {collector} with ABC. I'm calling about the $64,700.00 past due on your account, including invoice #{inv1}.
Customer: Yeah, I know. Honestly we're fed up with the service delays this quarter.
Customer: We've already been talking to another carrier and may be moving our business to UPS.
Collector: I'm sorry to hear about the delays. I can loop in your account executive to review the service issues.
Customer: That's fine, but I won't pay the late fees. Those are ridiculous.
Collector: I understand. Can we at least agree on a payment for the undisputed freight charges?
Customer: I need to check with my CFO. Call me back next week.
Collector: Will do. I'll also have Sales reach out about the service concerns."""

T_BROKEN = """Collector: Hi {contact}, it's {collector} from ABC AR. Last time we spoke you promised a payment on invoice #{inv1} by the 15th, but we haven't received it.
Customer: Yes, sorry, we missed the payment. Our controller was out.
Collector: I understand. When can we expect it?
Customer: We will pay the full $15,600.00 on {date_str} by ACH. I've already scheduled the payment.
Collector: Thank you. I'll note that commitment and check the account the day after.
Customer: Thanks, appreciate your patience."""

T_INFO = """Collector: Hello, this is {collector} from ABC Accounts Receivable calling for {contact}.
Customer: Hi, yes.
Collector: Just a courtesy call. Invoice #{inv1} is coming due next week, and I wanted to confirm you received it.
Customer: Yes, we have it. It's in our approval queue, no problem.
Collector: Great. Would you like a copy of the proof of delivery for your records?
Customer: Sure, that would be helpful. Thanks for the heads up."""

T_CARD = """Customer: Hi, this is {contact}. I got your voicemail about invoice #{inv1}.
Collector: Thanks for calling back, this is {collector}. The invoice for $9,800.00 is about four weeks past due.
Customer: Sorry about that. I can pay $4,900.00 tomorrow with a credit card and the rest on {date_str}.
Collector: That works. I'll send you the secure payment portal link.
Customer: Perfect, thank you."""

# customer_idx -> list of (days_ago, hour, duration_seconds, direction, template)
CALLS = {
    0: [(2, 10, 412, "Outbound", T_PROMISE), (21, 14, 238, "Outbound", T_INFO)],
    1: [(1, 11, 655, "Outbound", T_DISPUTE), (30, 9, 190, "Outbound", T_INFO)],
    2: [(5, 15, 175, "Outbound", T_INFO)],
    3: [(3, 13, 520, "Outbound", T_HARDSHIP), (34, 10, 300, "Outbound", T_PROMISE)],
    4: [(0, 9, 344, "Outbound", T_BROKEN), (20, 16, 401, "Outbound", T_PROMISE)],
    5: [(4, 12, 210, "Inbound", T_PAID)],
    6: [(1, 15, 732, "Outbound", T_CHURN), (14, 11, 480, "Outbound", T_HARDSHIP), (45, 10, 260, "Outbound", T_INFO)],
    7: [(6, 10, 198, "Outbound", T_INFO)],
    8: [(2, 14, 389, "Outbound", T_PROMISE), (16, 9, 502, "Outbound", T_DISPUTE)],
    9: [(8, 11, 165, "Outbound", T_INFO)],
    10: [(0, 13, 610, "Outbound", T_DISPUTE), (12, 15, 275, "Outbound", T_PAID)],
    11: [(1, 10, 233, "Inbound", T_CARD), (25, 14, 318, "Outbound", T_BROKEN)],
}

# Calls older than this are pre-analyzed so the dashboards have history; recent ones are analyzed on first open.
PRE_ANALYZE_OLDER_THAN_DAYS = 10


def seed_if_empty(db: Session) -> bool:
    if db.scalar(select(func.count()).select_from(Collector)):
        return False

    collectors = [Collector(full_name=n, email=e, region=r) for n, e, r in COLLECTORS]
    db.add_all(collectors)
    db.flush()

    today = date.today()
    customers = []
    for row in CUSTOMERS:
        (cidx, account, contact, company, phone, alt, email, address, shipping, home, office,
         status, ar, overdue, dpd, risk) = row
        customers.append(Customer(
            collector_id=collectors[cidx].id, account_number=account, full_name=contact, company_name=company,
            phone_number=phone, alternate_phone_number=alt, email=email, address=address,
            shipping_address=shipping, home_address=home, office_address=office, status=status,
            ar_balance=Decimal(str(ar)), overdue_amount=Decimal(str(overdue)), days_past_due=dpd, risk_level=risk,
        ))
    db.add_all(customers)
    db.flush()

    to_analyze = []
    for cust_idx, calls in CALLS.items():
        cust = customers[cust_idx]
        collector = collectors[CUSTOMERS[cust_idx][0]]
        acct_num = cust.account_number.split("-")[1]
        for n, (days_ago, hour, duration, direction, template) in enumerate(calls):
            call_day = today - timedelta(days=days_ago)
            transcript = template.format(
                collector=collector.full_name, contact=cust.full_name,
                inv1=f"INV-{acct_num}-{n}1", inv2=f"INV-{acct_num}-{n}2",
                date_str=(call_day + timedelta(days=7)).strftime("%B %d").replace(" 0", " "),
            )
            call = CallLog(
                customer_id=cust.id, collector_id=collector.id,
                call_datetime=datetime.combine(call_day, time(hour, 0), tzinfo=timezone.utc),
                duration_seconds=duration, direction=direction, transcript=transcript, analysis_status="Pending",
            )
            db.add(call)
            if days_ago > PRE_ANALYZE_OLDER_THAN_DAYS:
                to_analyze.append(call)
            if cust.last_contact_date is None or call_day > cust.last_contact_date:
                cust.last_contact_date = call_day
    db.commit()

    # History is analyzed with the offline engine so seeding never calls an external API.
    for call in to_analyze:
        db.refresh(call)
        result = RuleBasedAnalyzer().analyze(call.transcript, call.call_datetime.date(), call.customer.full_name)
        apply_analysis(call, result, "rules")
    db.commit()
    return True
