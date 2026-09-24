import { Suspense, lazy, useEffect } from "react";
import { Outlet, useLocation } from "react-router";

import { StatusMessage } from "@/components/StatusMessage/StatusMessage";
import { isSignedIn, redirectToSignIn } from "@/lib/auth";

import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

import styles from "./Shell.module.css";

const LANDING_PATH = "/";

const LandingScreen = lazy(async () => ({
  default: (await import("@/screens/landing/LandingScreen")).LandingScreen,
}));

export function Shell() {
  const { pathname, search } = useLocation();
  const signedIn = isSignedIn();
  const landing = !signedIn && pathname === LANDING_PATH;

  useEffect(() => {
    if (!signedIn && !landing) {
      void redirectToSignIn(`${pathname}${search}`);
    }
  }, [landing, pathname, search, signedIn]);

  if (landing) {
    return (
      <Suspense fallback={<StatusMessage />}>
        <LandingScreen />
      </Suspense>
    );
  }

  if (!signedIn) {
    return null;
  }

  return (
    <div className={styles.shell}>
      <Sidebar />
      <div className={styles.main}>
        <TopBar />
        <main className={styles.content}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
