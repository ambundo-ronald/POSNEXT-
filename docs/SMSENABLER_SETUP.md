# SMS Enabler Setup Guide for POS Next

SMS Enabler is a Kenyan payment integration that allows you to receive M-Pesa paybill payments via SMS. POS Next can automatically match incoming SMS payments to customer invoices and link them during checkout.

## 📋 Prerequisites

1. **SMS Enabler Account**: Sign up at [SMS Enabler](https://www.smsenabler.com/)
2. **M-Pesa Paybill Business**: Your business registered with Safaricom M-Pesa
3. **ERPNext Instance**: POS Next module installed
4. **Phone Mode of Payment**: Configured in ERPNext with proper accounts
5. **Public URL**: Your ERPNext instance must be accessible from the internet

---

## 🔧 Setup Steps

### Step 1: Configure ERPNext Backend

#### 1.1 Create "Phone" Mode of Payment

1. Go to **ERPNext** → **Accounting** → **Mode of Payment**
2. Create a new Mode of Payment:
   - **Name**: `Phone` (or similar identifier)
   - **Type**: `Phone`
   - **Enabled**: ✅ Check

3. Add Mode of Payment Accounts for your company:
   - Click **Add** in the "Accounts" table
   - **Company**: Your operating company
   - **Default Account**: Select your cash/receivables account (e.g., `Cash - KES` or `Undeposited Funds`)
   - **Save**

#### 1.2 Configure Site-Wide SMS Enabler in POS Settings

1. Open POS Next.
2. Open **POS Settings** for any POS Profile.
3. Go to **Sales Management**.
4. Enable **Site SMS Enabler**.
5. Save the settings. POS Next will generate one site-wide webhook token and webhook URL.
6. Copy the webhook URL.
7. Copy the token separately for SMS Enabler's **Tag** field.

> **Important**: SMS Enabler normally accepts one forwarding URL per device. POS Next therefore uses one site-wide webhook for all POS Profiles. The **SMS Payment Reconciliation** mode remains per POS Profile.
>
> **Security Note**: Protect this token. Regenerate it from POS Settings if it is exposed.

---

### Step 2: Configure SMS Enabler Service

#### 2.1 Register Your Webhook URL

1. Log in to **SMS Enabler Console**: https://console.smsenabler.com/
2. Go to **Settings** → **API Webhooks** or **SMS Forwarding**
3. Add a new webhook with:
   - **URL**: Paste the webhook URL copied from POS Settings.
   - **Method**: POST
   - **Tag**: Paste the webhook token copied from POS Settings. You can also send the same token in the `X-SMS-Enabler-Token` header if your SMS Enabler version supports custom headers.

4. **Test the webhook** (SMS Enabler will send a test request)
5. Save configuration

#### 2.2 Configure SMS Parsing

SMS Enabler should forward SMS messages with the following information:
- **sender**: SMS sender, for example `MPESA`
- **text**: Raw SMS message body
- **scts**: SMS timestamp, if available
- **tag**: The webhook token copied from POS Settings, if you are not using the token in the URL

The parser reads the raw SMS text and extracts:
- **Payer Name**: Who sent the money
- **Payer Phone**: Phone number of sender
- **Amount**: Payment amount (KES/KSH)
- **Transaction ID**: M-Pesa confirmation code
- **Account Reference**: Optional paybill account reference

**Example SMS format** (what your customers receive):
```
TransactionID: ABC123D4E5
Amount: KES 5000
From: JOHN DOE
For: Account/Invoice
```

---

### Step 3: Configure POS Profile

#### 3.1 Set Default Phone Mode of Payment

1. Go to **POS Profile** in ERPNext
2. Open your active POS Profile
3. In the **Payments** section, add `Phone` as a payment mode:
   - Click **Add** row
   - **Mode of Payment**: `Phone`
   - **Enabled**: ✅ Check
4. **Save** the POS Profile

#### 3.2 Configure SMS Reconciliation Mode

1. In **POS Settings**, choose **SMS Payment Reconciliation**:
   - **SMS Reconciliation Mode**: Select one:
     - `Manual`: Manual payment selection during checkout
     - `Suggested`: Auto-suggest matching payments (default)
     - `Auto`: Automatically add exact amount matches

2. **Save** the settings.

---

### Step 4: Test the Integration

#### 4.1 Verify SMS Reception

1. Send a test SMS to your SMS Enabler paybill number:
   ```
   Send to Paybill
   [Account number: your-account]
   Amount: 100 KES
   ```

2. Check **SMS Enabler Payment Register** in POS Next:
   - Go to **Desk** → Search **SMS Enabler Payment Register**
   - You should see the received SMS with:
     - ✅ Status: `Pending` or `Parsed`
     - Amount: `100.00` KES
     - Payer details extracted

3. If status shows `Failed Parse`, the SMS format isn't recognized. Verify:
   - Amount in SMS (look for KES/KSH)
   - Transaction ID format (should be 6+ alphanumeric chars)

#### 4.2 Test POS Payment Selection

1. Open **POS Sale**
2. Add items to cart and proceed to **Payment**
3. You should see:
   - "Quick Pay - SMS Enabler" section if SMS settings are configured
   - Or "Checking SMS Enabler setup..." while loading
4. Click **"Find SMS Payments"** button
5. Enter 3+ characters to search (searches by name, phone, transaction ID, account)
6. Select matching payments
7. Click **"Add Selected"** to link payments

---

### Step 5: Configure Payment Matching Rules

#### 5.1 Automatic Matching Criteria

SMS Enabler automatically scores payments based on:

| Criteria | Points | Example |
|----------|--------|---------|
| **Exact Amount** | 70 | Invoice 5000, Payment 5000 |
| **Close Amount** | 35 | Invoice 5000, Payment 5020 (±2%) |
| **Same Phone** | 25 | Customer & Payer phone match |
| **Name Match** | 10 | Names share 3+ letter words |
| **Today** | 10 | Payment received today |
| **Has Reference** | 5 | Account reference included |

**Match Levels**:
- 🟢 **High** (90+): Auto-suggest in "Suggested" mode
- 🟡 **Suggested** (60-89): Show in search results
- 🔴 **Low** (<60): Show but requires manual verification

#### 5.2 Improve Matching

To improve matching accuracy:

1. **Ensure customer has phone number**:
   - Go to **Customer** form
   - Add **Mobile No** or linked **Contact** with phone

2. **Use consistent account references**:
   - Train staff to include invoice/account number in SMS

3. **Keep Mode of Payment account updated**:
   - Ensure account exists and is active in your company

---

## 🔍 Troubleshooting

### Issue: "SMS Enabler setup is not available"

**Cause**: Mode of Payment not configured
- **Fix**: Create `Phone` mode of payment with account setup (see Step 1.1)

### Issue: SMS payments not showing in POS

**Cause**: Webhooks not receiving SMS
- **Check**:
  1. Is your ERPNext publicly accessible? (`https://your-domain/`)
  2. Is webhook URL correct in SMS Enabler console?
  3. Is SMS Enabler enabled in POS Settings, and is the copied webhook token current?
  4. Check Frappe error logs: **Desk** → **Error Log**

```bash
# Check webhook logs
cd frappe-bench
bench doctor
bench logs -f
```

### Issue: SMS marked as "Failed Parse"

**Cause**: Amount or Transaction ID not extracted
- **Solution**:
  1. Go to SMS record in **SMS Enabler Payment Register**
  2. Check **Raw Message** field
  3. Ensure message contains:
     - Amount with KES/KSH currency indicator
     - Transaction ID (6+ alphanumeric characters)
  4. Verify format matches examples expected by SMS Enabler

### Issue: Payment matched to wrong invoice

**Cause**: Multiple invoices with same amount
- **Fix**:
  1. Use account reference in SMS (customer account/invoice number)
  2. Manually verify before confirming payment
  3. Check customer phone number accuracy

---

## 🚀 Advanced Configuration

### Custom SMS Parser (Advanced)

If your SMS format is non-standard, modify the parser in:

**File**: `pos_next/api/smsenabler_mpesa.py`

Functions to customize:
- `_parse_amount()` - Extract currency amount
- `_parse_transaction_id()` - Extract transaction code
- `_parse_payer_phone()` - Extract sender phone
- `_parse_account_reference()` - Extract customer account

### Webhook Signature Verification

For enhanced security, SMS Enabler can sign webhooks. Add to your configuration:

Store any advanced webhook secret in site configuration only if you customize the receiver to validate signatures. The normal token is managed in POS Settings.

Then verify signature in API before processing.

### Reconciliation Automation

For `Auto` mode reconciliation, adjust scoring thresholds in:
- `_score_payment_match()` function in `smsenabler_mpesa.py`
- Default threshold: 90+ points for auto-add

---

## 📊 Monitoring

### View SMS Payment History

1. Go to **SMS Enabler Payment Register** list
2. Filter by:
   - **Status**: Pending, Matched, Consumed, Duplicate
   - **Received At**: Date range
   - **Company**: Your operating company

3. Analyze metrics:
   - Total pending payments
   - Parse success rate
   - Match accuracy

### Linked Invoices

When a payment is used:
- **Status**: Changed to `Consumed`
- **Sales Invoice**: Linked to created invoice
- **Payment Entry**: Linked to accounting entry

---

## ✅ Integration Checklist

- [ ] SMS Enabler account created and verified
- [ ] `Phone` Mode of Payment created
- [ ] Mode of Payment account linked to company
- [ ] SMS Enabler enabled in POS Settings
- [ ] Webhook URL copied from POS Settings
- [ ] Webhook URL registered in SMS Enabler console
- [ ] Webhook tested successfully
- [ ] POS Profile updated with Phone payment mode
- [ ] SMS Reconciliation Mode configured in POS Settings
- [ ] Test SMS sent and received
- [ ] SMS parsed correctly in Payment Register
- [ ] POS payment dialog shows SMS section
- [ ] First payment linked and invoice created
- [ ] Invoice marked Consumed after linking
- [ ] Accounting entries created correctly

---

## 📞 Support

- **SMS Enabler Docs**: https://www.smsenabler.com/docs
- **ERPNext Docs**: https://docs.erpnext.com
- **POS Next Issues**: https://github.com/ambundo-ronald/POSNEXT-/issues
- **Community Chat**: Telegram - POS Next Community

---

## 🔐 Security Best Practices

1. **Protect your token**:
   - Never share the webhook URL publicly
   - Regenerate the token from POS Settings if it is exposed
   - Rotate token regularly

2. **Use HTTPS only**:
   - Webhook URL must be HTTPS
   - Validate SSL certificates

3. **Validate source**:
   - Verify webhook comes from SMS Enabler IP
   - Add IP whitelisting if available

4. **Monitor failed attempts**:
   - Check Error Log regularly
   - Alert on authentication failures
