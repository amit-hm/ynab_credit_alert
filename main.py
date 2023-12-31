from datetime import datetime, timedelta
import os
import textwrap

from ynab import YNABClient
from utils import setup_environment_vars, combine_names
import smtplib
from email.message import EmailMessage

class ynab_credit_alert():
    def __init__(self, ynab_personal_access_token, ynab_budget_name, cut_off_days) -> None:
        self.ynab = YNABClient(ynab_personal_access_token)

        self.ynab_budget_id = self.ynab.get_budget_id(ynab_budget_name)

        # get dates
        today = datetime.now().date()
        self.cutoff_date = today - timedelta(days=int(cut_off_days))

    def is_payment(self, ynab_account_id):
        transactions = self.ynab.get_transactions(self.ynab_budget_id, ynab_account_id, since_date=self.cutoff_date)
        
        for t in transactions['data']['transactions']:
            if 'Transfer' in t['payee_name'] and t['amount']>0 and t['cleared']=='cleared':
                return True
        return False
    
    def get_credit_accounts(self):
        accounts = self.ynab.get_accounts(self.ynab_budget_id)
        credit_accounts = []
        for a in accounts['data']['accounts']:
            if a['type'] == 'creditCard':
                credit_accounts.append(a['name'])
        return credit_accounts
    
    def check_accounts(self):
        due_accounts = []
        credit_accounts = self.get_credit_accounts()
        for account_name in credit_accounts:
            account_id = self.ynab.get_account_id(self.ynab_budget_id, account_name)
            is_paid = self.is_payment(account_id)
            if not is_paid:
                due_accounts.append(account_name)

        # if any account(s) are due
        if due_accounts:
            due_accounts = combine_names(due_accounts)
            
            subject = "YNAB Credit Alert - Important! Payment due!"
            message = textwrap.dedent(f"""\
            Hello,

            The following accounts are due for payment and have not been paid in the last 
            {cut_off_days} days:
            {due_accounts}

            Please make the payment to avoid the account becoming due.

            Note: The way this works is that the code checks if a payment has been done, 
                  so if there was no balance to pay off, it would trigger a false alert.
            
            Best regards,
            YNAB Credit Alert
            """)
        else:   # if all accounts are in good standing
            subject = "YNAB Credit Alert - All good!"
            message = textwrap.dedent(f"""\
            Hello,

            All your accounts have been paid.
            
            Best regards,
            YNAB Credit Alert
            """)
        return subject, message

    def send_email(self, smtp_server, port, username, password, from_address, recipient, subject, body):
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = from_address
        msg['To'] = recipient

        try:
            with smtplib.SMTP(smtp_server, port) as server:
                server.starttls()  # Secure the connection
                server.login(username, password)
                server.send_message(msg)
                print("Email sent successfully!")
        except Exception as e:
            print(f"Error sending email: {e}")

if __name__=="__main__":
    # load environment variables from yaml file (locally)
    setup_environment_vars()

    # ynab creds
    ynab_budget_name = os.environ.get('YNAB_BUDGET_NAME')
    ynab_personal_access_token = os.environ.get('YNAB_PERSONAL_ACCESS_TOKEN')
    cut_off_days = os.environ.get('CUT_OFF_DAYS')
    smtp_server = os.environ.get('SMTP_SERVER')
    port = os.environ.get('PORT')
    sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
    from_address = os.environ.get('FROM_ADDRESS')
    recipient = os.environ.get('RECIPIENT')

    a = ynab_credit_alert(ynab_personal_access_token, ynab_budget_name, cut_off_days)
    subject, body = a.check_accounts()

    username = 'apikey'
    password = 'SG.' + sendgrid_api_key
    a.send_email(smtp_server, port, username, password, from_address, recipient, subject, body)