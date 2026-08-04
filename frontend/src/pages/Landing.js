import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLanguage } from '../contexts/LanguageContext';
import { useAuth } from '../contexts/AuthContext';
import { useConfig } from '../contexts/ConfigContext';
import { DOMAIN } from '../config/site';
import { ArrowRight, Plus, Lightning } from '@phosphor-icons/react';

// ═══════════════════════════════════════════════════════════════════
//  Landing — Terminal-aesthetic, bright emerald, light-first.
// ═══════════════════════════════════════════════════════════════════

const SECTION_LABEL = 'font-mono text-xs lowercase text-primary tracking-wider';

const RECORD_TYPE_CLASS = {
  A: 'text-[hsl(var(--rec-a))]',
  AAAA: 'text-[hsl(var(--rec-aaaa))]',
  CNAME: 'text-[hsl(var(--rec-cname))]',
  NS: 'text-[hsl(var(--rec-ns))]',
};

export default function Landing() {
  const { lang } = useLanguage();
  const { user } = useAuth();
  const navigate = useNavigate();
  const config = useConfig();
  const DNS_DOMAIN = config.dns_domain || DOMAIN; // Cloudflare zone — used ONLY where subdomains are created
  const SITE_DOMAIN = config.install_domain || window.location.hostname.replace(/^www\./, '') || DNS_DOMAIN;
  const isFa = lang === 'fa';

  // Telegram support link — auto-synced with the admin "Telegram username" setting.
  // Prefer the resolved URL from /config; fall back to building it from the id.
  const telegramUrl = config.telegram_url
    || (config.telegram_id ? `https://t.me/${config.telegram_id.replace(/^@/, '')}` : '');

  const [plans, setPlans] = useState([]);
  const [openFaq, setOpenFaq] = useState(-1);

  useEffect(() => {
    fetch(`${process.env.REACT_APP_BACKEND_URL}/api/plans`).then(r => r.json()).then(data => {
      const arr = Array.isArray(data) ? data : (data?.plans || []);
      setPlans(arr.sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0)));
    }).catch(() => {});
  }, []);

  const goAuth = () => navigate(user ? '/dashboard' : '/register');

  const previewRecords = [
    { type: 'A', name: 'myapp', value: '192.0.2.10', ttl: 'auto' },
    { type: 'AAAA', name: 'myapp', value: '2001:db8::1', ttl: 'auto' },
    { type: 'CNAME', name: 'www', value: `myapp.${DNS_DOMAIN}`, ttl: '300' },
    { type: 'NS', name: '@', value: 'ns1.cloudflare…', ttl: '86400' },
  ];

  const featureCards = [
    {
      tag: isFa ? 'رکورد' : 'records',
      title: isFa ? 'رایگان همیشگی' : 'Free Forever',
      desc: isFa ? 'تا ۲ رکورد DNS کاملاً رایگان بساز. بدون نیاز به کارت اعتباری.' : 'Create up to 2 DNS records completely free. No credit card needed.',
    },
    {
      tag: isFa ? 'سرعت' : 'speed',
      title: isFa ? 'سریع همچو برق' : 'Lightning Fast',
      desc: isFa ? 'انتشار DNS در چند ثانیه از طریق شبکه‌ی جهانی Cloudflare.' : "DNS propagation in seconds via Cloudflare's global network.",
    },
    {
      tag: isFa ? 'شبکه' : 'network',
      title: isFa ? 'انواع رکورد' : 'Multiple Record Types',
      desc: isFa ? 'پشتیبانی کامل از A، AAAA، CNAME و NS.' : 'Full support for A, AAAA, CNAME, and NS record types.',
    },
    {
      tag: isFa ? 'امنیت' : 'security',
      title: isFa ? 'امن از طراحی' : 'Secure by Default',
      desc: isFa ? 'تحت محافظت زیرساخت سطح سازمانی Cloudflare.' : "Protected by Cloudflare's enterprise-grade security infrastructure.",
    },
    {
      tag: isFa ? 'داشبورد' : 'dashboard',
      title: isFa ? 'داشبورد ساده' : 'Easy Dashboard',
      desc: isFa ? 'یک داشبورد روشن برای ساخت و مدیریت همه‌ی رکوردها.' : 'Intuitive dashboard to create and manage all your DNS records.',
    },
    {
      tag: isFa ? 'دی‌ان‌اس واقعی' : 'real dns',
      title: isFa ? 'رکوردهای واقعی DNS' : 'Real DNS Records',
      desc: isFa ? 'رکوردها روی زیرساخت Cloudflare ساخته می‌شن. واقعی، نه پراکسی.' : "Records are created on Cloudflare's infrastructure. Real DNS, not a proxy.",
    },
  ];

  const faqItems = [
    {
      q: isFa ? 'چه نوع رکوردهایی پشتیبانی می‌شن؟' : 'What DNS record types are supported?',
      a: isFa ? 'رکوردهای A، AAAA، CNAME و NS — تمام چیزی که برای راه‌اندازی یک سایت لازم داری.' : 'A, AAAA, CNAME, and NS — everything you need to launch a site or service.',
    },
    {
      q: isFa ? 'چقدر طول می‌کشه تغییرات اعمال بشن؟' : 'How quickly do changes propagate?',
      a: isFa ? 'تغییرات معمولاً در کمتر از ۶۰ ثانیه روی شبکه‌ی جهانی Cloudflare فعال می‌شن.' : 'Changes go live globally in under 60 seconds via Cloudflare.',
    },
    {
      q: isFa ? 'پلن رایگان موجوده؟' : 'Is there a free plan?',
      a: isFa ? 'بله. پلن Free شامل ۲ رکورد رایگان همیشگی هست — بدون کارت اعتباری.' : 'Yes. The Free plan gives you 2 records forever — no credit card.',
    },
    {
      q: isFa ? 'چطور رکورد نامحدود بگیرم؟' : 'How to get unlimited records?',
      a: isFa ? 'پلن Pro رو از طریق تلگرام درخواست بده — تیم ما در همان روز پاسخ می‌ده.' : 'Reach out via Telegram for the Pro plan — we usually respond the same day.',
    },
    {
      q: isFa ? 'Cloudflare Proxy چیست؟' : 'What is Cloudflare Proxy?',
      a: isFa ? 'یک لایه‌ی محافظ که ترافیک سایتت رو از طریق شبکه‌ی Cloudflare عبور می‌ده — DDoS، CDN و WAF رایگان.' : "A protective layer that routes your site's traffic through Cloudflare — DDoS, CDN, and WAF, free.",
    },
  ];

  const marqueeWords = [
    isFa ? 'Anycast DNS' : 'Anycast DNS',
    isFa ? 'DNSSEC آماده' : 'DNSSEC Ready',
    isFa ? 'حفاظت DDoS' : 'DDoS Protected',
    isFa ? 'انتشار <۶۰ ثانیه' : '<60s Propagation',
    isFa ? 'CDN جهانی' : 'Global CDN',
    isFa ? 'REST API' : 'REST API',
    isFa ? 'Cloudflare Proxy' : 'Cloudflare Proxy',
    isFa ? 'رایگان همیشگی' : 'Free Forever',
  ];

  return (
    <div className="min-h-screen bg-background text-foreground page-mount">
      {/* ═══════════════════════════════ HERO ═══════════════════════════════ */}
      <section className="border-b border-border" data-testid="hero-section">
        <div className="mx-auto max-w-7xl px-6 lg:px-12 pt-12 pb-16 lg:pt-20 lg:pb-24">
          <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-start">
            {/* LEFT */}
            <div>
              <div className="font-mono text-sm text-muted-foreground" dir="ltr">
                <span className="text-primary">$</span> dns --init --zone <span className="text-foreground">{DNS_DOMAIN}</span>
              </div>
              <h1 className="font-display text-5xl lg:text-7xl xl:text-8xl font-black tracking-tighter leading-[0.95] mt-6" data-testid="hero-title">
                {isFa ? (
                  <>
                    {'مدیریت '}
                    <span className="text-primary">DNS</span>
                    <br />
                    {'رایگان'}
                  </>
                ) : (
                  <>
                    Free <span className="text-primary">DNS</span><br />Management
                  </>
                )}
              </h1>
              <p className="mt-6 text-base lg:text-lg text-muted-foreground max-w-md leading-relaxed">
                {isFa
                  ? `زیردامنه‌ی رایگانت رو روی ${DNS_DOMAIN} بگیر. رکوردهای A، AAAA و CNAME رو با داشبورد قدرتمند ما مدیریت کن.`
                  : `Get your free subdomain on ${DNS_DOMAIN}. Manage A, AAAA, and CNAME records with our powerful dashboard.`}
              </p>

              {/* Record-type pills — single row */}
              <div className="flex flex-nowrap items-center gap-1.5 mt-7 overflow-x-auto no-scrollbar" dir="ltr">
                {['A', 'AAAA', 'CNAME', 'NS'].map((t) => (
                  <span
                    key={t}
                    className="font-mono text-[11px] px-2.5 py-1 border border-border bg-card text-foreground flex-shrink-0"
                  >
                    {t}
                  </span>
                ))}
                <span className="font-mono text-[11px] text-muted-foreground ms-1 inline-flex items-center gap-1 flex-shrink-0 whitespace-nowrap">
                  <Lightning weight="fill" className="w-3.5 h-3.5 text-primary" />
                  {isFa ? 'انتشار <۶۰s' : '<60s propagation'}
                </span>
              </div>

              {/* CTAs */}
              <div className="flex flex-wrap items-center gap-3 mt-8">
                <button
                  onClick={goAuth}
                  className="btn-geo h-12 px-6 bg-primary text-primary-foreground font-mono text-sm lowercase inline-flex items-center gap-3"
                  data-testid="hero-cta-primary"
                >
                  {isFa ? 'شروع کن' : 'get started'}
                  <ArrowRight weight="bold" className="w-4 h-4 rtl-flip" />
                </button>
                <button
                  onClick={() => document.getElementById('pricing')?.scrollIntoView({ behavior: 'smooth' })}
                  className="h-12 px-6 border border-border bg-card hover:bg-secondary font-mono text-sm lowercase transition-colors"
                  data-testid="hero-cta-secondary"
                >
                  {isFa ? 'دیدن پلن‌ها' : 'view plans'}
                </button>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-6 mt-10 pt-8 border-t border-border" dir="ltr">
                <div>
                  <div className="font-display text-3xl lg:text-4xl font-black tracking-tighter">2,400+</div>
                  <div className="font-mono text-[11px] text-muted-foreground lowercase mt-1">{isFa ? 'کاربر' : 'users'}</div>
                </div>
                <div>
                  <div className="font-display text-3xl lg:text-4xl font-black tracking-tighter">8,100+</div>
                  <div className="font-mono text-[11px] text-muted-foreground lowercase mt-1">{isFa ? 'رکورد' : 'records'}</div>
                </div>
                <div>
                  <div className="font-display text-3xl lg:text-4xl font-black tracking-tighter">99.9%</div>
                  <div className="font-mono text-[11px] text-muted-foreground lowercase mt-1">{isFa ? 'پایداری' : 'uptime'}</div>
                </div>
              </div>
            </div>

            {/* RIGHT — Terminal preview */}
            <div className="border border-border bg-card" data-testid="hero-console" dir="ltr">
              <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-secondary/40">
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-destructive/70" />
                  <span className="w-2.5 h-2.5 rounded-full bg-warning/70" />
                  <span className="w-2.5 h-2.5 rounded-full bg-success/70" />
                  <span className="ms-2 font-mono text-[11px] text-muted-foreground">~/zone/{DNS_DOMAIN}</span>
                </div>
                <span className="font-mono text-[10px] text-success inline-flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-success" /> live
                </span>
              </div>

              <div className="p-4 lg:p-6 font-mono text-xs space-y-3">
                <div className="text-muted-foreground">
                  <span className="text-success">$</span> dns list --zone {DNS_DOMAIN}
                </div>
                <div className="text-muted-foreground">{'> Fetching records...'}</div>

                {/* Mini table */}
                <div className="border border-border mt-4">
                  <div className="grid grid-cols-12 gap-2 px-3 py-2 bg-secondary/40 border-b border-border text-[10px] uppercase tracking-widest text-muted-foreground">
                    <div className="col-span-2">type</div>
                    <div className="col-span-3">name</div>
                    <div className="col-span-5">value</div>
                    <div className="col-span-2 text-end">ttl</div>
                  </div>
                  {previewRecords.map((r, i) => (
                    <div key={i} className="grid grid-cols-12 gap-2 px-3 py-2.5 border-b last:border-b-0 border-border">
                      <div className={`col-span-2 ${RECORD_TYPE_CLASS[r.type]} font-bold`}>{r.type}</div>
                      <div className="col-span-3 truncate">{r.name}</div>
                      <div className="col-span-5 truncate text-muted-foreground">{r.value}</div>
                      <div className="col-span-2 text-end text-muted-foreground">{r.ttl}</div>
                    </div>
                  ))}
                </div>

                <div className="flex items-center justify-between pt-1">
                  <span className="text-muted-foreground">{previewRecords.length} records found</span>
                  <span className="text-success">propagated ✓</span>
                </div>
                <div className="text-success pt-1">$ <span className="caret-blink ms-0.5"></span></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Marquee strip */}
      <div className="border-b border-border bg-card overflow-hidden" data-testid="marquee">
        <div className="flex animate-marquee whitespace-nowrap py-3" dir="ltr">
          {[...Array(2)].map((_, k) => (
            <div key={k} className="flex items-center gap-8 ps-8 font-mono text-xs text-muted-foreground">
              {marqueeWords.map((w, i) => (
                <React.Fragment key={i}>
                  <span>{w}</span>
                  <span className="text-primary">•</span>
                </React.Fragment>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* ═══════════════════════════════ FEATURES ═══════════════════════════════ */}
      <section id="features" className="border-b border-border" data-testid="features-section">
        <div className="mx-auto max-w-7xl px-6 lg:px-12 py-16 lg:py-24">
          <div className="mb-10 lg:mb-14">
            <span className={SECTION_LABEL}>// {isFa ? 'قابلیت‌ها' : 'features'}</span>
            <h2 className="font-display text-4xl lg:text-6xl font-black tracking-tighter mt-3">
              {isFa ? `چرا ${SITE_DOMAIN}؟` : `Why ${SITE_DOMAIN}?`}
            </h2>
            <p className="mt-3 text-base text-muted-foreground">
              {isFa ? 'هر چیزی که برای مدیریت قابل اطمینان DNS لازم داری.' : 'Everything you need for reliable DNS management.'}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-border border border-border">
            {featureCards.map((f, i) => (
              <div key={i} className="bg-card p-6 lg:p-8 hover:bg-secondary/30 transition-colors group" data-testid={`feature-card-${i}`}>
                <div className={SECTION_LABEL}>{f.tag}</div>
                <h3 className="font-display text-2xl font-bold tracking-tight mt-2 mb-3">{f.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════ PRICING ═══════════════════════════════ */}
      <section id="pricing" className="border-b border-border bg-secondary/20" data-testid="pricing-section">
        <div className="mx-auto max-w-7xl px-6 lg:px-12 py-16 lg:py-24">
          <div className="mb-10 lg:mb-14">
            <span className={SECTION_LABEL}>// {isFa ? 'پلن‌ها' : 'pricing'}</span>
            <h2 className="font-display text-4xl lg:text-6xl font-black tracking-tighter mt-3">
              {isFa ? 'قیمت‌گذاری ساده' : 'Simple Pricing'}
            </h2>
          </div>

          <div className={`grid gap-0 border border-border bg-background ${plans.length === 2 ? 'md:grid-cols-2' : 'md:grid-cols-3'}`}>
            {plans.map((p, i) => {
              const priceStr = (isFa ? p.price_fa : p.price) || '';
              const isFree = /free|رایگان|^0$/i.test(priceStr);
              const handlePlanClick = () => {
                if (isFree) {
                  goAuth();
                } else if (telegramUrl) {
                  window.open(telegramUrl, '_blank', 'noopener,noreferrer');
                } else {
                  goAuth();
                }
              };
              return (
              <div
                key={p.plan_id}
                className={`p-6 lg:p-8 ${i > 0 ? 'border-t md:border-t-0 md:border-s border-border' : ''} ${p.popular ? 'bg-primary/5 dark:bg-primary/10 ring-2 ring-primary ring-inset relative' : ''}`}
                data-testid={`plan-card-${p.plan_id}`}
              >
                {p.popular && (
                  <div className="absolute -top-px end-4 px-3 py-1 bg-primary text-primary-foreground font-mono text-[10px] uppercase tracking-widest">
                    ★ {isFa ? 'محبوب' : 'popular'}
                  </div>
                )}
                <div className={SECTION_LABEL}>
                  plan:{p.name?.toLowerCase()}
                </div>

                <div className="mt-6 mb-6 pb-6 border-b border-border">
                  <span className="font-display text-4xl lg:text-5xl font-black tracking-tighter">
                    {(isFa ? p.price_fa : p.price) || (isFa ? 'تماس' : 'Contact')}
                  </span>
                  <div className="font-mono text-xs text-muted-foreground mt-2 lowercase">
                    {p.record_limit === 0 ? (isFa ? 'رکورد نامحدود' : 'unlimited records') : (isFa ? `حداکثر ${p.record_limit} رکورد` : `${p.record_limit} records max`)}
                  </div>
                </div>

                <ul className="text-sm space-y-2 mb-8">
                  <li className="flex items-start gap-2">
                    <Plus weight="bold" className="w-3.5 h-3.5 mt-0.5 text-primary flex-shrink-0" />
                    <span>{p.record_limit === 0 ? (isFa ? 'رکورد نامحدود' : 'Unlimited Records') : (isFa ? `${p.record_limit} رکورد DNS` : `${p.record_limit} DNS Records`)}</span>
                  </li>
                  {((isFa ? (p.features_fa?.length ? p.features_fa : p.features) : p.features) || []).filter(f => f && f.trim() !== '+').map((feat, fi) => (
                    <li key={fi} className="flex items-start gap-2">
                      <Plus weight="bold" className="w-3.5 h-3.5 mt-0.5 text-primary flex-shrink-0" />
                      <span>{feat}</span>
                    </li>
                  ))}
                </ul>

                <button
                  onClick={handlePlanClick}
                  className={`w-full h-12 font-mono text-sm lowercase transition-colors inline-flex items-center justify-center gap-2 ${p.popular ? 'bg-primary text-primary-foreground hover:bg-primary/90' : 'border border-foreground text-foreground hover:bg-foreground hover:text-background'}`}
                  data-testid={`plan-cta-${p.plan_id}`}
                >
                  {isFree
                    ? (isFa ? 'شروع کن' : 'get started')
                    : (isFa ? 'تماس با ما' : 'contact us')}
                  <ArrowRight weight="bold" className="w-4 h-4 rtl-flip" />
                </button>
              </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════ FAQ ═══════════════════════════════ */}
      <section id="faq" className="border-b border-border" data-testid="faq-section">
        <div className="mx-auto max-w-4xl px-6 lg:px-12 py-16 lg:py-24">
          <div className="mb-10">
            <span className={SECTION_LABEL}>// {isFa ? 'سوالات' : 'faq'}</span>
            <h2 className="font-display text-4xl lg:text-6xl font-black tracking-tighter mt-3">
              {isFa ? 'سوالات متداول' : 'Frequently Asked'}
            </h2>
          </div>
          <div className="border border-border bg-card">
            {faqItems.map((item, i) => (
              <button
                key={i}
                onClick={() => setOpenFaq(openFaq === i ? -1 : i)}
                className={`w-full text-start p-5 lg:p-6 border-t first:border-t-0 border-border hover:bg-secondary/30 transition-colors ${openFaq === i ? 'bg-secondary/30' : ''}`}
                data-testid={`faq-${i}`}
              >
                <div className="flex items-start justify-between gap-4">
                  <span className="font-display text-lg lg:text-xl font-bold tracking-tight flex-1">
                    <span className="text-primary me-3 font-mono text-sm">{(i + 1).toString().padStart(2, '0')}</span>
                    {item.q}
                  </span>
                  <span className={`font-mono text-2xl text-primary transition-transform leading-none mt-1 ${openFaq === i ? 'rotate-45' : ''}`}>+</span>
                </div>
                {openFaq === i && (
                  <p className="text-sm text-muted-foreground leading-relaxed mt-4 ms-9">{item.a}</p>
                )}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════ FINAL CTA ═══════════════════════════════ */}
      <section className="border-y border-border bg-secondary/30 dark:bg-secondary/40 relative overflow-hidden" data-testid="final-cta">
        <div className="bg-grid-fine absolute inset-0 opacity-30" />
        <div className="relative mx-auto max-w-7xl px-6 lg:px-12 py-20 lg:py-32 text-center">
          <span className={SECTION_LABEL}>// {isFa ? 'پایان' : 'end'}</span>
          <h2 className="font-display font-black tracking-tighter leading-[0.92] mt-4 text-[clamp(3rem,9vw,8rem)] text-foreground">
            {isFa ? 'آماده‌ای راه‌اندازی کنی؟' : 'Ready to deploy?'}
          </h2>
          <p className="mt-6 text-base lg:text-lg text-muted-foreground max-w-xl mx-auto">
            {isFa ? 'اولین رکورد رو در کمتر از ۶۰ ثانیه منتشر کن.' : 'Propagate your first record in under 60 seconds.'}
          </p>

          <div className="mt-10 inline-flex flex-wrap items-stretch border border-border bg-card max-w-full">
            <span className="font-mono text-sm px-4 py-3 text-primary self-center" dir="ltr">
              <span>$</span> {SITE_DOMAIN.split('.')[0]} register --free
            </span>
            <button
              onClick={goAuth}
              className="h-12 px-6 bg-primary text-primary-foreground font-mono text-sm lowercase inline-flex items-center gap-2 hover:opacity-90 transition-opacity"
              data-testid="final-cta-button"
            >
              {isFa ? 'اجرا' : 'run'}
              <ArrowRight weight="bold" className="w-4 h-4 rtl-flip" />
            </button>
          </div>

          <p className="mt-6 font-mono text-xs text-muted-foreground lowercase">
            {isFa ? 'بدون نیاز به کارت اعتباری' : 'no credit card required'}
          </p>
        </div>
      </section>

      {/* ═══════════════════════════════ FOOTER ═══════════════════════════════ */}
      <footer className="border-t border-border bg-card" data-testid="footer">
        <div className="mx-auto max-w-7xl px-6 lg:px-12 py-10 grid grid-cols-2 md:grid-cols-4 gap-8">
          <div className="col-span-2 md:col-span-1">
            <div className="font-display text-2xl font-black tracking-tighter">
              <span className="text-primary">▌</span> {SITE_DOMAIN}
            </div>
            <p className="font-mono text-xs text-muted-foreground mt-2 lowercase">
              {isFa ? 'مدیریت دامنه‌ی رایگان و سریع' : 'free, fast domain management'}
            </p>
          </div>
          {[
            { title: isFa ? 'محصول' : 'product', items: [
              { label: isFa ? 'قابلیت‌ها' : 'features', href: '#features' },
              { label: isFa ? 'پلن‌ها' : 'pricing', href: '#pricing' },
              { label: isFa ? 'سوالات' : 'faq', href: '#faq' },
            ]},
            { title: isFa ? 'حساب' : 'account', items: [
              { label: isFa ? 'ورود' : 'log in', href: '/login' },
              { label: isFa ? 'ثبت‌نام' : 'sign up', href: '/register' },
            ]},
            { title: isFa ? 'پشتیبانی' : 'support', items: [
              { label: isFa ? 'تلگرام' : 'telegram', href: telegramUrl || '#', external: !!telegramUrl },
              { label: 'github', href: 'https://github.com/admin6501/ddns-khalilv2', external: true },
            ]},
          ].map((col) => (
            <div key={col.title}>
              <div className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground mb-3">{col.title}</div>
              <ul className="space-y-2 font-mono text-sm lowercase">
                {col.items.map((it) => (
                  <li key={it.label}>
                    <a
                      href={it.href}
                      {...(it.external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
                      className="text-foreground/70 hover:text-primary transition-colors"
                      data-testid={`footer-link-${it.label}`}
                    >{it.label}</a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="border-t border-border">
          <div className="mx-auto max-w-7xl px-6 lg:px-12 py-4 flex flex-col md:flex-row items-center justify-between gap-2 font-mono text-[10px] tracking-widest text-muted-foreground lowercase">
            <p>© {new Date().getFullYear()} {SITE_DOMAIN} · {isFa ? 'تمامی حقوق محفوظ است' : 'all rights reserved'}</p>
            <p dir="ltr">▌ free · fast · secure</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
