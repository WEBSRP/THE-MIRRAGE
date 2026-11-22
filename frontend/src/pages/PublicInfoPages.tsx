import { Link } from 'react-router-dom';
import type { ReactNode } from 'react';
import { Icon, Mark } from '../components/Icon';
import { SiteFooter } from '../components/SiteFooter';
import { useApp } from '../state/AppState';
import './public-info.css';

function PublicPage({ children }: { children: ReactNode }) {
  return (
    <div className="public-info">
      <header className="public-info-header">
        <Link className="wordmark" to="/" aria-label="MIRRAGE home"><Mark /><span>MIRRAGE</span></Link>
      </header>
      <main className="public-info-main">{children}</main>
      <SiteFooter />
    </div>
  );
}

export function NotFoundPage() {
  const { isAuthenticated } = useApp();
  return (
    <PublicPage>
      <section className="public-info-error" aria-labelledby="missing-page-title">
        <p className="public-info-error-code">404</p>
        <h1 id="missing-page-title">Page not found</h1>
        <p>Check the address or choose where to go next.</p>
        <div className="public-info-actions">
          <Link className="ui-button ui-button-primary ui-button-medium" to="/">
            <Icon name="arrow-left" size={16} /> Back to home
          </Link>
          {isAuthenticated && (
            <Link className="ui-button ui-button-secondary ui-button-medium" to="/dashboard">Open dashboard</Link>
          )}
        </div>
      </section>
    </PublicPage>
  );
}

export function AboutPage() {
  return (
    <PublicPage>
      <article className="public-info-copy">
        <h1>About us</h1>
        <p>MIRRAGE is an independent educational cybersecurity project. It gives curious learners a hands-on space to practice through capture-the-flag challenges.</p>
        <h2>How the range works</h2>
        <p>Players start an isolated challenge environment and connect to it over OpenVPN. The challenges reward observation, experimentation, and careful investigation. Keep your testing within the environment assigned to your session.</p>
        <h2>Play MIRRAGE</h2>
        <p>The range is available on request. Use the social links below to send your preferred date, time, and time zone.</p>
      </article>
    </PublicPage>
  );
}

export function PrivacyPage() {
  return (
    <PublicPage>
      <article className="public-info-copy">
        <h1>Privacy policy</h1>
        <p>This policy explains what information MIRRAGE uses when you visit the site, sign in, or play in the range.</p>
        <h2>Account and sign-in information</h2>
        <p>We use your email address to send sign-in codes and manage your account. If you join the waiting list, we use it to let you know when a session slot is ready. We store your username and account details so you can return to your profile and challenge progress. We use sign-in request records and an IP-derived identifier to limit abuse.</p>
        <h2>Sessions and challenge activity</h2>
        <p>We keep session records, challenge results, and activity logs to operate the range and track progress. Other players can see your username and score on the leaderboard. We process VPN credentials, assigned addresses, connection times, and traffic totals to manage access and show connection status. Protect your downloaded VPN file as you would a password.</p>
        <h2>Browser storage</h2>
        <p>The site uses browser storage to keep you signed in, remember display preferences, and track which notices you have dismissed. You can clear this information in your browser settings. Clearing browser storage signs you out and resets local preferences.</p>
        <h2>Service providers and external links</h2>
        <p>We use Vercel to host the website, Cloudflare to deliver API traffic, Amazon Web Services to host the platform and database, and an email delivery provider to send sign-in codes. When you follow a social link, that platform handles your visit under its own privacy policy.</p>
        <h2>Retention and privacy requests</h2>
        <p>Retention varies by record. Account and challenge records support your profile and progress, while operational records help us maintain the service, troubleshoot issues, and investigate abuse. For questions about retention or to request access, correction, or deletion, email <a href="mailto:hello@themirrage.me">hello@themirrage.me</a>.</p>
      </article>
    </PublicPage>
  );
}
