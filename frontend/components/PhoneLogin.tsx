"use client";

import { FormEvent, useState } from "react";
import { confirmPhoneOtp, requestPhoneOtp } from "@/lib/api";
import { friendlyError } from "@/lib/errors";

const INDIA_MOBILE_PATTERN = /^[6-9][0-9]{9}$/;
const indiaPhone = (localNumber: string) => `+91${localNumber}`;

export type PhoneLoginProps = {
  tenantId: string;
  onVerified: (sessionToken: string) => void;
  /** Optional heading copy shown above the phone-entry step. */
  title?: string;
  description?: string;
};

// Shared phone -> OTP verification step-flow used anywhere a citizen needs to
// prove ownership of a phone number (currently /report and /my-reports).
export default function PhoneLogin({
  tenantId,
  onVerified,
  title = "Enter Your Phone Number",
  description = "We'll send a one-time code to your WhatsApp account.",
}: PhoneLoginProps) {
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");

  const [sending, setSending] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [resending, setResending] = useState(false);

  const [phoneError, setPhoneError] = useState("");
  const [codeError, setCodeError] = useState("");
  const [notice, setNotice] = useState("");

  async function sendCode(e?: FormEvent) {
    e?.preventDefault();
    setPhoneError("");
    setNotice("");

    if (!phone) {
      setPhoneError("Please enter your phone number.");
      return;
    }
    if (!INDIA_MOBILE_PATTERN.test(phone)) {
      setPhoneError("Enter a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9.");
      return;
    }

    setSending(true);
    try {
      await requestPhoneOtp(tenantId, indiaPhone(phone));
      setStep("code");
      setNotice(`A verification code was sent on WhatsApp to +91 ${phone}.`);
    } catch (cause: any) {
      const msg = /429/.test(cause?.message ?? "")
        ? "You've requested a code too recently. Please wait a minute before trying again."
        : friendlyError(cause);
      setPhoneError(msg);
    } finally {
      setSending(false);
    }
  }

  async function resendCode() {
    setResending(true);
    setCodeError("");
    setNotice("");
    try {
      await requestPhoneOtp(tenantId, indiaPhone(phone));
      setNotice("A new verification code was sent on WhatsApp.");
    } catch (cause: any) {
      const msg = /429/.test(cause?.message ?? "")
        ? "You've requested a code too recently. Please wait a minute before trying again."
        : friendlyError(cause);
      setCodeError(msg);
    } finally {
      setResending(false);
    }
  }

  async function verifyCode(e: FormEvent) {
    e.preventDefault();
    setCodeError("");

    if (code.trim().length !== 6) {
      setCodeError("Please enter the 6-digit code.");
      return;
    }

    setVerifying(true);
    try {
      const token = await confirmPhoneOtp(tenantId, indiaPhone(phone), code.trim());
      onVerified(token);
    } catch (cause: any) {
      setCodeError(/400/.test(cause?.message ?? "") ? "That code is incorrect or has expired. Please try again." : friendlyError(cause));
    } finally {
      setVerifying(false);
    }
  }

  return (
    <section className="panel">
      {step === "phone" && (
        <>
          <div className="panel-head">
            <div>
              <h3>{title}</h3>
              <p>{description}</p>
            </div>
          </div>
          <form className="form-stack" onSubmit={sendCode}>
            <label htmlFor="phone">
              Phone Number
              <span className="india-phone-input">
                <span className="country-code" aria-label="India country code">🇮🇳 +91</span>
                <input
                  id="phone"
                  type="tel"
                  inputMode="numeric"
                  pattern="[6-9][0-9]{9}"
                  maxLength={10}
                  placeholder="98765 43210"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value.replace(/\D/g, "").slice(0, 10))}
                  required
                />
              </span>
              <small>India mobile numbers only</small>
            </label>

            <div aria-live="polite">
              {phoneError && (
                <div className="alert error" role="alert">
                  {phoneError}
                </div>
              )}
            </div>

            <button className="button full" type="submit" disabled={sending}>
              {sending ? (
                <>
                  <span className="spinner" />
                  Sending code…
                </>
              ) : (
                "Send WhatsApp Code"
              )}
            </button>
          </form>
        </>
      )}

      {step === "code" && (
        <>
          <div className="panel-head">
            <div>
              <h3>Enter Verification Code</h3>
              <p>Enter the 6-digit code sent on WhatsApp to +91 {phone}.</p>
            </div>
          </div>
          <form className="form-stack" onSubmit={verifyCode}>
            <label htmlFor="code">
              Verification Code
              <input
                id="code"
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={6}
                placeholder="123456"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                required
              />
            </label>

            <div aria-live="polite">
              {notice && !codeError && <div className="alert success">{notice}</div>}
              {codeError && (
                <div className="alert error" role="alert">
                  {codeError}
                </div>
              )}
            </div>

            <button className="button full" type="submit" disabled={verifying}>
              {verifying ? (
                <>
                  <span className="spinner" />
                  Verifying…
                </>
              ) : (
                "Verify"
              )}
            </button>

            <button
              type="button"
              className="button ghost"
              onClick={resendCode}
              disabled={resending}
              style={{ fontSize: 13 }}
            >
              {resending ? "Resending…" : "Resend code"}
            </button>
          </form>
        </>
      )}
    </section>
  );
}
