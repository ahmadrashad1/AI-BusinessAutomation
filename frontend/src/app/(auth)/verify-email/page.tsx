"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { authApi } from "@/lib/api/auth";

type Status = "pending" | "success" | "error";

export default function VerifyEmailPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [status, setStatus] = useState<Status>("pending");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("No verification token found in the URL.");
      return;
    }

    authApi
      .verifyEmail(token)
      .then(() => {
        setStatus("success");
        setTimeout(() => router.push("/login"), 2000);
      })
      .catch((err) => {
        setStatus("error");
        setMessage(
          err?.response?.data?.error?.message ?? "Verification failed. The link may be expired or already used."
        );
      });
  }, [token, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4">
      <div className="max-w-md w-full text-center space-y-4">
        {status === "pending" && (
          <>
            <div className="text-4xl animate-spin">⏳</div>
            <p className="text-gray-600">Verifying your email…</p>
          </>
        )}
        {status === "success" && (
          <>
            <div className="text-5xl">✅</div>
            <h2 className="text-2xl font-bold text-gray-900">Email verified!</h2>
            <p className="text-gray-600">Redirecting you to login…</p>
          </>
        )}
        {status === "error" && (
          <>
            <div className="text-5xl">❌</div>
            <h2 className="text-2xl font-bold text-gray-900">Verification failed</h2>
            <p className="text-gray-600">{message}</p>
            <Link href="/login" className="inline-block mt-4 text-indigo-600 hover:text-indigo-500 font-medium">
              Back to login
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
