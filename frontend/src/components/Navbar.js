import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { useLanguage } from '../contexts/LanguageContext';
import { Button } from '../components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import { Sun, Moon, Menu, X, LogOut, LayoutDashboard, User, ShieldCheck, ChevronDown, Terminal, Activity } from 'lucide-react';
import { DOMAIN } from '../config/site';
import { useConfig } from '../contexts/ConfigContext';

export default function Navbar() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { t, lang, toggleLang } = useLanguage();
  const location = useLocation();
  const navigate = useNavigate();
  const config = useConfig();
  const DNS_DOMAIN = config.install_domain || config.dns_domain || DOMAIN;
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const isActive = (path) => location.pathname === path;
  const isAdmin = user?.role === 'admin';

  const navLinks = user
    ? []
    : [
        { path: '/#features', label: lang === 'fa' ? 'قابلیت‌ها' : 'features', isHash: true },
        { path: '/#pricing', label: lang === 'fa' ? 'پلن‌ها' : 'pricing', isHash: true },
        { path: '/#faq', label: lang === 'fa' ? 'سوالات' : 'faq', isHash: true },
      ];

  const handleNavClick = (link) => {
    setMobileOpen(false);
    if (link.isHash) {
      if (location.pathname !== '/') {
        navigate('/');
        setTimeout(() => {
          document.getElementById(link.path.replace('/#', ''))?.scrollIntoView({ behavior: 'smooth' });
        }, 100);
      } else {
        document.getElementById(link.path.replace('/#', ''))?.scrollIntoView({ behavior: 'smooth' });
      }
    } else {
      navigate(link.path);
    }
  };

  return (
    <nav
      className={`sticky top-0 z-50 glass-nav border-b transition-colors duration-300 ${
        scrolled ? 'border-border' : 'border-border/40'
      }`}
      data-testid="navbar"
    >

      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-14">
          {/* Logo — terminal style */}
          <Link to="/" className="flex items-center gap-2.5 group" data-testid="navbar-logo">
            <div className="w-8 h-8 flex items-center justify-center border border-border bg-card group-hover:border-primary transition-colors">
              <Terminal className="w-4 h-4 text-primary" strokeWidth={2.5} />
            </div>
            <div className="font-mono text-base font-bold tracking-tight lowercase">
              <span className="text-foreground">{DNS_DOMAIN.split('.')[0]}</span>
              <span className="text-muted-foreground">.{DNS_DOMAIN.split('.').slice(1).join('.')}</span>
              <span
                className="animate-blink inline-block align-middle ml-1 w-[7px] h-[15px] bg-primary translate-y-[-1px]"
                aria-hidden="true"
                data-testid="navbar-logo-caret"
              />
            </div>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden md:flex items-center gap-6">
            {navLinks.map((link) => (
              <button
                key={link.path}
                onClick={() => handleNavClick(link)}
                className={`text-sm font-mono lowercase transition-colors ${
                  isActive(link.path) ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
                }`}
                data-testid={`nav-link-${link.path.replace(/[/#]/g, '')}`}
              >
                {link.label}
              </button>
            ))}
          </div>

          {/* Right side */}
          <div className="hidden md:flex items-center gap-1.5">
            {/* Language toggle */}
            <button
              onClick={toggleLang}
              className="h-9 px-2.5 border border-border bg-card hover:border-primary hover:text-primary transition-colors text-xs font-mono lowercase"
              data-testid="language-toggle-button"
              aria-label="Toggle language"
            >
              {lang === 'en' ? 'fa' : 'en'}
            </button>

            {/* Theme toggle */}
            <button
              onClick={toggleTheme}
              className="w-9 h-9 border border-border bg-card hover:border-primary hover:text-primary transition-colors flex items-center justify-center"
              data-testid="theme-toggle-button"
              aria-label="Toggle theme"
            >
              {theme === 'dark' ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
            </button>

            {/* Auth */}
            {user ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    className="h-8 px-3 border border-border bg-card hover:border-primary transition-colors flex items-center gap-2 text-xs font-mono"
                    data-testid="user-menu-trigger"
                  >
                    <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full" />
                    <span className="max-w-[120px] truncate">{user.name || user.email}</span>
                    <ChevronDown className="w-3 h-3 opacity-60" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56 font-mono text-xs rounded-sm">
                  <DropdownMenuLabel className="text-[10px] uppercase tracking-widest text-muted-foreground">
                    user::session
                  </DropdownMenuLabel>
                  <div className="px-2 pb-2 text-xs">
                    <p className="truncate">{user.email}</p>
                    <p className="text-muted-foreground text-[10px] mt-1">plan: <span className="text-primary uppercase">{user.plan || 'free'}</span></p>
                  </div>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => navigate('/dashboard')} data-testid="menu-dashboard" className="rounded-none">
                    <LayoutDashboard className="w-3.5 h-3.5 me-2" />
                    {t('nav_dashboard')}
                  </DropdownMenuItem>
                  {isAdmin && (
                    <DropdownMenuItem onClick={() => navigate('/admin')} data-testid="menu-admin" className="rounded-none text-primary">
                      <ShieldCheck className="w-3.5 h-3.5 me-2" />
                      {t('nav_admin')}
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleLogout} className="text-destructive rounded-none" data-testid="menu-logout">
                    <LogOut className="w-3.5 h-3.5 me-2" />
                    {t('nav_logout')}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <div className="flex items-center gap-1.5 ms-1">
                <button
                  onClick={() => navigate('/login')}
                  className="h-9 px-3 text-sm font-mono lowercase text-muted-foreground hover:text-foreground transition-colors"
                  data-testid="nav-login-button"
                >
                  {lang === 'fa' ? 'ورود' : 'log in'}
                </button>
                <button
                  onClick={() => navigate('/register')}
                  className="h-9 px-4 bg-primary text-primary-foreground hover:bg-primary/90 text-sm font-mono lowercase font-semibold transition-colors flex items-center gap-1.5"
                  data-testid="nav-register-button"
                >
                  <span>{lang === 'fa' ? 'ثبت‌نام' : 'sign up'}</span>
                  <span className="opacity-70">→</span>
                </button>
              </div>
            )}
          </div>

          {/* Mobile menu toggle */}
          <div className="flex md:hidden items-center gap-1.5">
            <button onClick={toggleTheme} className="w-8 h-8 border border-border flex items-center justify-center" data-testid="mobile-theme-toggle">
              {theme === 'dark' ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
            </button>
            <button onClick={() => setMobileOpen(!mobileOpen)} className="w-8 h-8 border border-border flex items-center justify-center" data-testid="mobile-menu-toggle">
              {mobileOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div className="md:hidden border-t border-border py-3 space-y-1 animate-fade-in" data-testid="mobile-menu">
            {navLinks.map((link) => (
              <button
                key={link.path}
                onClick={() => handleNavClick(link)}
                className="block w-full text-start px-3 py-2.5 text-xs font-mono uppercase tracking-widest hover:bg-muted/60 hover:text-primary transition-colors"
              >
                <span className="text-primary me-2">$</span>{link.label}
              </button>
            ))}
            <button
              onClick={() => { toggleLang(); setMobileOpen(false); }}
              className="block w-full text-start px-3 py-2.5 text-xs font-mono uppercase tracking-widest hover:bg-muted/60 transition-colors"
            >
              <span className="text-primary me-2">$</span>
              {lang === 'en' ? 'SWITCH / FA' : 'SWITCH / EN'}
            </button>
            <div className="border-t border-border pt-2 mt-2 space-y-1.5">
              {user ? (
                <>
                  <button onClick={() => { navigate('/dashboard'); setMobileOpen(false); }} className="block w-full text-start px-3 py-2.5 text-xs font-mono uppercase tracking-widest hover:bg-muted/60 transition-colors">
                    <LayoutDashboard className="w-3.5 h-3.5 inline me-2" />{t('nav_dashboard')}
                  </button>
                  {isAdmin && (
                    <button onClick={() => { navigate('/admin'); setMobileOpen(false); }} className="block w-full text-start px-3 py-2.5 text-xs font-mono uppercase tracking-widest text-primary hover:bg-muted/60 transition-colors">
                      <ShieldCheck className="w-3.5 h-3.5 inline me-2" />{t('nav_admin')}
                    </button>
                  )}
                  <button onClick={() => { handleLogout(); setMobileOpen(false); }} className="block w-full text-start px-3 py-2.5 text-xs font-mono uppercase tracking-widest text-destructive hover:bg-destructive/10 transition-colors">
                    <LogOut className="w-3.5 h-3.5 inline me-2" />{t('nav_logout')}
                  </button>
                </>
              ) : (
                <>
                  <button onClick={() => { navigate('/login'); setMobileOpen(false); }} className="block w-full text-center px-3 py-2.5 text-xs font-mono uppercase tracking-widest border border-border hover:border-primary transition-colors">
                    {t('nav_login')}
                  </button>
                  <button onClick={() => { navigate('/register'); setMobileOpen(false); }} className="block w-full text-center px-3 py-2.5 text-xs font-mono uppercase tracking-widest bg-primary text-primary-foreground">
                    {t('nav_register')} →
                  </button>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
