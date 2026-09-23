import { useEffect } from "react";
import { Outlet, useLocation } from "react-router";

import { isSignedIn, redirectToSignIn } from "@/lib/auth";

import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

import styles from "./Shell.module.css";

export function Shell() {
  const { pathname, search } = useLocation();
  const signedIn = isSignedIn();

  useEffect(() => {
    if (!signedIn) {
      void redirectToSignIn(`${pathname}${search}`);
    }
  }, [pathname, search, signedIn]);

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
