import type { AppProps } from "next/app";
import Head from "next/head";
import localFont from "next/font/local";
import "../styles/globals.css";

const cookieRun = localFont({
  src: [
    { path: "../fonts/CookieRunRegular.woff", weight: "400", style: "normal" },
    { path: "../fonts/CookieRunBold.woff2", weight: "700", style: "normal" },
    { path: "../fonts/CookieRunBlack.woff2", weight: "900", style: "normal" },
  ],
  variable: "--font-sans",
});

export default function App({ Component, pageProps }: AppProps) {
  return (
    <>
      <Head>
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1, maximum-scale=1"
        />
      </Head>
      <div className={cookieRun.variable}>
        <Component {...pageProps} />
      </div>
    </>
  );
}
