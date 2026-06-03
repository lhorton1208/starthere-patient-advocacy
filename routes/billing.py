from datetime import date
from decimal import Decimal

from auth import employee_required
from forms import AccountForm, AccountSearchForm, BillingForm, InvoiceForm, empty_select
from models import (
    Account,
    Billing,
    Client,
    Encounter,
    Invoice,
    InvoiceItem,
    LookupList,
    Note,
    Patient,
    db,
)
from flask import Blueprint, flash, redirect, render_template, request, url_for

billing_bp = Blueprint("billing", __name__, url_prefix="/accounts")


def _populate_account_form(form, account=None):
    account_types = LookupList.query.filter_by(list_type="account_type").order_by(
        LookupList.name
    ).all()
    clients = Client.query.order_by(Client.name).all()
    patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()

    form.list_id.choices = empty_select("account type") + [
        (item.id, item.name) for item in account_types
    ]
    form.client_id.choices = empty_select("client") + [
        (c.id, c.display_name) for c in clients
    ]
    form.patient_id.choices = [(0, "None")] + [
        (p.id, p.full_name) for p in patients
    ]

    if account:
        form.list_id.data = account.list_id
        form.client_id.data = account.client_id
        form.patient_id.data = account.patient_id or 0
        form.name.data = account.name
        form.account_number.data = account.account_number
        form.balance.data = account.balance
        form.status.data = account.status


def _patient_notes_for_account(account):
    if not account.patient_id:
        return []
    return (
        Note.query.join(Encounter, Note.encounter_id == Encounter.id)
        .filter(Encounter.patient_id == account.patient_id)
        .order_by(Note.created_at.desc())
        .all()
    )


@billing_bp.route("/")
@employee_required
def list_accounts():
    search_form = AccountSearchForm(formdata=request.args)
    query = Account.query.join(Client)

    if search_form.q.data:
        term = f"%{search_form.q.data.strip()}%"
        query = query.filter(
            db.or_(
                Account.name.ilike(term),
                Account.account_number.ilike(term),
                Client.name.ilike(term),
            )
        )
    if search_form.status.data:
        query = query.filter(Account.status == search_form.status.data)

    accounts = query.order_by(Account.name).all()
    return render_template(
        "staff/billing/account_list.html",
        accounts=accounts,
        search_form=search_form,
    )


@billing_bp.route("/new", methods=["GET", "POST"])
@employee_required
def new_account():
    form = AccountForm()
    _populate_account_form(form)
    if form.validate_on_submit():
        account = Account(
            list_id=form.list_id.data,
            client_id=form.client_id.data,
            patient_id=form.patient_id.data or None,
            name=form.name.data.strip(),
            account_number=(form.account_number.data or "").strip() or None,
            balance=form.balance.data or Decimal("0"),
            status=form.status.data,
        )
        db.session.add(account)
        db.session.commit()
        flash("Account created successfully.", "success")
        return redirect(url_for("billing.view_account", account_id=account.id))
    return render_template("staff/billing/account_form.html", form=form, title="New Account")


@billing_bp.route("/<int:account_id>")
@employee_required
def view_account(account_id):
    account = Account.query.get_or_404(account_id)
    billings = account.billings.order_by(Billing.billed_at.desc()).all()
    invoices = account.invoices.order_by(Invoice.issue_date.desc()).all()
    return render_template(
        "staff/billing/account_detail.html",
        account=account,
        billings=billings,
        invoices=invoices,
    )


@billing_bp.route("/<int:account_id>/billing/new", methods=["GET", "POST"])
@employee_required
def new_billing(account_id):
    account = Account.query.get_or_404(account_id)
    form = BillingForm()

    notes = _patient_notes_for_account(account)
    if not notes:
        flash(
            "This account needs a linked patient with encounter notes before billing can be added.",
            "error",
        )
        return redirect(url_for("billing.view_account", account_id=account.id))

    form.note_id.choices = [
        (
            n.id,
            f"Note #{n.id} – {(n.content[:60] + '...') if len(n.content) > 60 else n.content}",
        )
        for n in notes
    ]

    if form.validate_on_submit():
        billing = Billing(
            note_id=form.note_id.data,
            account_id=account.id,
            description=(form.description.data or "").strip() or None,
            amount=form.amount.data,
        )
        account.balance = (account.balance or Decimal("0")) + form.amount.data
        db.session.add(billing)
        db.session.commit()
        flash("Billing record added successfully.", "success")
        return redirect(url_for("billing.view_account", account_id=account.id))

    return render_template(
        "staff/billing/billing_form.html",
        form=form,
        account=account,
    )


@billing_bp.route("/<int:account_id>/invoices/new", methods=["GET", "POST"])
@employee_required
def new_invoice(account_id):
    account = Account.query.get_or_404(account_id)
    form = InvoiceForm()
    if not form.invoice_number.data:
        form.invoice_number.data = f"INV-{account.id}-{date.today().strftime('%Y%m%d')}"

    if form.validate_on_submit():
        amount = form.quantity.data * form.unit_price.data
        invoice = Invoice(
            account_id=account.id,
            invoice_number=form.invoice_number.data.strip(),
            issue_date=form.issue_date.data,
            due_date=form.due_date.data,
            total=amount,
            status=form.status.data,
        )
        db.session.add(invoice)
        db.session.flush()
        db.session.add(
            InvoiceItem(
                invoice_id=invoice.id,
                description=form.description.data.strip(),
                quantity=form.quantity.data,
                unit_price=form.unit_price.data,
                amount=amount,
            )
        )
        db.session.commit()
        flash("Invoice created successfully.", "success")
        return redirect(url_for("billing.view_invoice", invoice_id=invoice.id))

    return render_template(
        "staff/billing/invoice_form.html",
        form=form,
        account=account,
    )


@billing_bp.route("/invoices/<int:invoice_id>")
@employee_required
def view_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    items = invoice.items.all()
    return render_template(
        "staff/billing/invoice_detail.html",
        invoice=invoice,
        items=items,
    )
