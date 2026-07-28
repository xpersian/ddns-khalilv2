import React, { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import { useAuth } from '../contexts/AuthContext';
import { adminAPI, activityAPI } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { Checkbox } from '../components/ui/checkbox';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../components/ui/dialog';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../components/ui/alert-dialog';
import { Switch } from '../components/ui/switch';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../components/ui/table';
import {
  Users, Server, Settings, Trash2, Eye, ArrowUpDown, Loader2, UserPlus,
  Plus, Save, RefreshCw, Crown, KeyRound, CreditCard, Pencil, Gift, Clock,
  X, ChevronLeft, ChevronRight, Copy, ClipboardCheck, Zap, CheckCircle2, XCircle,
  Database, Download, Upload, ToggleLeft, ToggleRight,
  Bot, Play, Square, Globe, Shield, Mail, Lock
} from 'lucide-react';
import { toast } from 'sonner';
import { DOMAIN } from '../config/site';
import { useConfig } from '../contexts/ConfigContext';
import { downloadBlob, fileTimestamp } from '../lib/utils';

export default function Admin() {
  const { t, lang } = useLanguage();
  const { user } = useAuth();
  const config = useConfig();
  const DNS_DOMAIN = config.dns_domain || DOMAIN;
  const [activeTab, setActiveTab] = useState('users');

  // Users
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [deleteUserId, setDeleteUserId] = useState(null);
  const [planDialogUser, setPlanDialogUser] = useState(null);
  const [selectedPlan, setSelectedPlan] = useState('free');
  const [planLoading, setPlanLoading] = useState(false);

  // Activity log state
  const [adminLogs, setAdminLogs] = useState([]);
  const [adminLogPage, setAdminLogPage] = useState(1);
  const [adminLogPages, setAdminLogPages] = useState(1);
  const [adminLogLoading, setAdminLogLoading] = useState(false);
  const [adminLogFilter, setAdminLogFilter] = useState('');

  // Password
  const [passwordDialogUser, setPasswordDialogUser] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [passwordLoading, setPasswordLoading] = useState(false);

  // Bulk selection
  const [selectedUserIds, setSelectedUserIds] = useState(new Set());
  const [showBulkPlanDialog, setShowBulkPlanDialog] = useState(false);
  const [bulkPlan, setBulkPlan] = useState('free');
  const [bulkLoading, setBulkLoading] = useState(false);
  const [showBulkDeleteDialog, setShowBulkDeleteDialog] = useState(false);

  // Records
  const [allRecords, setAllRecords] = useState([]);
  const [recordsLoading, setRecordsLoading] = useState(true);
  const [userRecordsDialog, setUserRecordsDialog] = useState(null);
  const [userRecords, setUserRecords] = useState([]);
  const [deleteRecordId, setDeleteRecordId] = useState(null);

  // Create record
  const [showCreateRecordDialog, setShowCreateRecordDialog] = useState(false);
  const [createRecordForm, setCreateRecordForm] = useState({
    user_id: '', name: '', record_type: 'A', content: '', ttl: 1, proxied: false, zone_id: ''
  });
  const [createRecordLoading, setCreateRecordLoading] = useState(false);
  const [createRecordError, setCreateRecordError] = useState('');

  // Admin CSV import
  const [showAdminImportDialog, setShowAdminImportDialog] = useState(false);
  const [adminImportCsvText, setAdminImportCsvText] = useState('');
  const [adminImportLoading, setAdminImportLoading] = useState(false);
  const [adminImportResult, setAdminImportResult] = useState(null);

  // Google OAuth settings
  const [googleOAuth, setGoogleOAuth] = useState({ enabled: false, client_id: '', client_secret: '', client_secret_masked: '', has_secret: false });
  const [googleOAuthSaving, setGoogleOAuthSaving] = useState(false);

  // Record types
  const [recordTypes, setRecordTypes] = useState([]);
  const [recordTypesSaving, setRecordTypesSaving] = useState('');

  // Plans
  const [plans, setPlans] = useState([]);
  const [plansLoading, setPlansLoading] = useState(true);
  const [showPlanDialog, setShowPlanDialog] = useState(false);
  const [editingPlan, setEditingPlan] = useState(null);
  const [planForm, setPlanForm] = useState({
    plan_id: '', name: '', name_fa: '', price: '', price_fa: '',
    record_limit: 0, features: '', features_fa: '', popular: false, sort_order: 0
  });
  const [planFormLoading, setPlanFormLoading] = useState(false);
  const [planFormError, setPlanFormError] = useState('');
  const [deletePlanId, setDeletePlanId] = useState(null);

  // Settings
  const [settings, setSettings] = useState({
    telegram_id: '', telegram_url: '', contact_message_en: '', contact_message_fa: '',
    referral_bonus_per_invite: 1
  });
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);

  // Bot management
  const [botStatus, setBotStatus] = useState({ has_token: false, masked_token: '', admin_id: '', bot_running: false, bot_username: '' });
  const [botLoading, setBotLoading] = useState(false);
  const [newBotToken, setNewBotToken] = useState('');
  const [newAdminId, setNewAdminId] = useState('');
  const [botActionLoading, setBotActionLoading] = useState('');
  const [showTokenInput, setShowTokenInput] = useState(false);

  // Zones management
  const [zones, setZones] = useState([]);
  const [zonesLoading, setZonesLoading] = useState(false);
  const [showAddZone, setShowAddZone] = useState(false);
  const [newZoneId, setNewZoneId] = useState('');
  const [newZoneToken, setNewZoneToken] = useState('');
  const [addZoneLoading, setAddZoneLoading] = useState(false);

  // CF API Token management
  const [cfTokenInfo, setCfTokenInfo] = useState({ has_token: false, masked_token: '' });
  const [newCfToken, setNewCfToken] = useState('');
  const [showCfTokenInput, setShowCfTokenInput] = useState(false);
  const [cfTokenLoading, setCfTokenLoading] = useState(false);
  const [cfTestLoading, setCfTestLoading] = useState(false);
  const [cfTestResult, setCfTestResult] = useState(null);

  // Backup
  const [backupSettings, setBackupSettings] = useState({
    enabled: false, bot_token_set: false, masked_token: '', admin_id: '', interval_minutes: 60,
    last_backup: null, last_backup_size: null
  });
  const [backupBotToken, setBackupBotToken] = useState('');
  const [backupLoading, setBackupLoading] = useState(false);
  const [backupNowLoading, setBackupNowLoading] = useState(false);
  const [backupRestoreLoading, setBackupRestoreLoading] = useState(false);
  const [backupTestLoading, setBackupTestLoading] = useState(false);

  // SMTP / Email verification
  const [smtpStatus, setSmtpStatus] = useState({ has_smtp: false, smtp_email: '', email_verification_enabled: false });
  const [smtpLoading, setSmtpLoading] = useState(false);
  const [newSmtpEmail, setNewSmtpEmail] = useState('');
  const [newSmtpPassword, setNewSmtpPassword] = useState('');
  const [smtpSaving, setSmtpSaving] = useState(false);

  // Email signup form toggle
  const [emailSignupEnabled, setEmailSignupEnabled] = useState(true);
  const [emailSignupSaving, setEmailSignupSaving] = useState(false);

  const fetchEmailSignupStatus = useCallback(async () => {
    try {
      const r = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/admin/auth/signup-status`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      const d = await r.json();
      setEmailSignupEnabled(!!d.email_signup_enabled);
    } catch {}
  }, []);

  const handleToggleEmailSignup = async () => {
    setEmailSignupSaving(true);
    try {
      const newVal = !emailSignupEnabled;
      const r = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/admin/auth/toggle-email-signup`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({ enabled: newVal }),
      });
      if (!r.ok) throw new Error('failed');
      setEmailSignupEnabled(newVal);
      toast.success(
        lang === 'fa'
          ? (newVal ? 'فرم ثبت‌نام ایمیلی فعال شد' : 'فرم ثبت‌نام ایمیلی غیرفعال شد')
          : (newVal ? 'Email signup form enabled' : 'Email signup form disabled')
      );
    } catch {
      toast.error(lang === 'fa' ? 'خطا در تغییر وضعیت' : 'Failed to update');
    } finally {
      setEmailSignupSaving(false);
    }
  };

  const fetchUsers = useCallback(async () => {
    setUsersLoading(true);
    try {
      const res = await adminAPI.listUsers();
      setUsers(res.data.users || []);
    } catch { toast.error('Failed to load users'); }
    finally { setUsersLoading(false); }
  }, []);

  const fetchAllRecords = useCallback(async () => {
    setRecordsLoading(true);
    try {
      const res = await adminAPI.listAllRecords();
      setAllRecords(res.data.records || []);
    } catch { toast.error('Failed to load records'); }
    finally { setRecordsLoading(false); }
  }, []);

  const fetchPlans = useCallback(async () => {
    setPlansLoading(true);
    try {
      const res = await adminAPI.listPlans();
      setPlans(res.data.plans || []);
    } catch { toast.error('Failed to load plans'); }
    finally { setPlansLoading(false); }
  }, []);

  const fetchSettings = useCallback(async () => {
    setSettingsLoading(true);
    try {
      const res = await adminAPI.getSettings();
      const tgId = (res.data.telegram_id || '').replace(/^@/, '');
      let tgUrl = res.data.telegram_url || '';
      // Keep the (disabled) URL field in sync with the username, even if the
      // stored value is stale/base-only (e.g. after a backup restore).
      if (tgId && (!tgUrl || tgUrl.replace(/\/+$/, '') === 'https://t.me')) {
        tgUrl = `https://t.me/${tgId}`;
      }
      setSettings({
        telegram_id: tgId,
        telegram_url: tgUrl,
        contact_message_en: res.data.contact_message_en || '',
        contact_message_fa: res.data.contact_message_fa || '',
        referral_bonus_per_invite: res.data.referral_bonus_per_invite ?? 1,
      });
    } catch { toast.error('Failed to load settings'); }
    finally { setSettingsLoading(false); }
  }, []);

  const fetchAdminLogs = useCallback(async (page = 1, action = '') => {
    setAdminLogLoading(true);
    try {
      const res = await activityAPI.getAdminLogs(page, 30, '', action);
      setAdminLogs(res.data.logs || []);
      setAdminLogPages(res.data.pages || 1);
      setAdminLogPage(res.data.page || 1);
    } catch { /* ignore */ }
    setAdminLogLoading(false);
  }, []);

  const fetchBotStatus = useCallback(async () => {
    setBotLoading(true);
    try {
      const res = await adminAPI.getBotStatus();
      setBotStatus(res.data);
      setNewAdminId(res.data.admin_id || '');
    } catch { /* ignore */ }
    setBotLoading(false);
  }, []);

  const fetchZones = useCallback(async () => {
    setZonesLoading(true);
    try {
      const res = await adminAPI.listZones();
      setZones(res.data.zones || []);
    } catch { /* ignore */ }
    setZonesLoading(false);
  }, []);

  const fetchCfToken = useCallback(async () => {
    try {
      const res = await adminAPI.getCfToken();
      setCfTokenInfo(res.data);
    } catch { /* ignore */ }
  }, []);

  const fetchBackupSettings = useCallback(async () => {
    try {
      const res = await adminAPI.getBackupSettings();
      setBackupSettings(res.data);
    } catch { /* ignore */ }
  }, []);

  const fetchSmtpStatus = useCallback(async () => {
    setSmtpLoading(true);
    try {
      const res = await adminAPI.getSmtpStatus();
      setSmtpStatus(res.data);
    } catch { /* ignore */ }
    setSmtpLoading(false);
  }, []);

  const fetchGoogleOAuth = useCallback(async () => {
    try {
      const res = await adminAPI.getGoogleOAuth();
      setGoogleOAuth(p => ({ ...p, ...res.data, client_secret: '' }));
    } catch { /* ignore */ }
  }, []);

  const fetchRecordTypes = useCallback(async () => {
    try {
      const res = await adminAPI.getRecordTypes();
      setRecordTypes(res.data.types || []);
    } catch { /* ignore */ }
  }, []);

  const handleToggleRecordType = async (type, enabled) => {
    setRecordTypesSaving(type);
    const next = recordTypes.map(rt => rt.type === type ? { ...rt, enabled } : rt);
    const enabledList = next.filter(rt => rt.enabled).map(rt => rt.type);
    try {
      const res = await adminAPI.updateRecordTypes(enabledList);
      setRecordTypes(res.data.types || next);
      toast.success(lang === 'fa' ? 'نوع رکورد به‌روزرسانی شد' : 'Record type updated');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed');
    } finally { setRecordTypesSaving(''); }
  };

  useEffect(() => {
    fetchUsers(); fetchAllRecords(); fetchPlans(); fetchSettings(); fetchAdminLogs(); fetchBotStatus(); fetchZones(); fetchSmtpStatus(); fetchCfToken(); fetchBackupSettings(); fetchGoogleOAuth(); fetchEmailSignupStatus(); fetchRecordTypes();
  }, [fetchUsers, fetchAllRecords, fetchPlans, fetchSettings, fetchAdminLogs, fetchBotStatus, fetchZones, fetchSmtpStatus, fetchCfToken, fetchBackupSettings, fetchGoogleOAuth, fetchEmailSignupStatus, fetchRecordTypes]);

  // === User actions ===
  const handleDeleteUser = async () => {
    if (!deleteUserId) return;
    try {
      await adminAPI.deleteUser(deleteUserId);
      toast.success('User deleted');
      setDeleteUserId(null);
      fetchUsers(); fetchAllRecords();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
  };

  const handleChangePlan = async () => {
    if (!planDialogUser) return;
    setPlanLoading(true);
    try {
      await adminAPI.updateUserPlan(planDialogUser.id, selectedPlan);
      toast.success(`Plan updated to ${selectedPlan}`);
      setPlanDialogUser(null);
      fetchUsers();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
    finally { setPlanLoading(false); }
  };

  const handleChangePassword = async () => {
    if (!passwordDialogUser || newPassword.length < 6) return;
    setPasswordLoading(true);
    try {
      await adminAPI.changeUserPassword(passwordDialogUser.id, newPassword);
      toast.success(t('admin_password_changed'));
      setPasswordDialogUser(null);
      setNewPassword('');
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
    finally { setPasswordLoading(false); }
  };

  const handleViewUserRecords = async (u) => {
    setUserRecordsDialog(u);
    try {
      const res = await adminAPI.getUserRecords(u.id);
      setUserRecords(res.data.records || []);
    } catch { toast.error('Failed to load records'); }
  };

  // === Bulk actions ===
  const toggleUserSelection = (userId) => {
    setSelectedUserIds(prev => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  };

  const toggleSelectAll = () => {
    const selectable = users.filter(u => u.role !== 'admin');
    if (selectedUserIds.size === selectable.length) {
      setSelectedUserIds(new Set());
    } else {
      setSelectedUserIds(new Set(selectable.map(u => u.id)));
    }
  };

  const handleBulkPlanChange = async () => {
    setBulkLoading(true);
    try {
      const res = await adminAPI.bulkUpdatePlan([...selectedUserIds], bulkPlan);
      toast.success(t('admin_bulk_plan_updated').replace('{count}', res.data.updated_count));
      setShowBulkPlanDialog(false);
      setSelectedUserIds(new Set());
      fetchUsers();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
    finally { setBulkLoading(false); }
  };

  const handleBulkDelete = async () => {
    setBulkLoading(true);
    try {
      const res = await adminAPI.bulkDeleteUsers([...selectedUserIds]);
      toast.success(t('admin_bulk_deleted').replace('{count}', res.data.deleted_count));
      setShowBulkDeleteDialog(false);
      setSelectedUserIds(new Set());
      fetchUsers();
      fetchAllRecords();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
    finally { setBulkLoading(false); }
  };

  // === Record actions ===
  const handleDeleteRecord = async () => {
    if (!deleteRecordId) return;
    try {
      await adminAPI.deleteRecord(deleteRecordId);
      toast.success('Record deleted');
      setDeleteRecordId(null);
      fetchAllRecords();
      if (userRecordsDialog) handleViewUserRecords(userRecordsDialog);
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
  };

  const handleCreateRecord = async () => {
    setCreateRecordError('');
    setCreateRecordLoading(true);
    try {
      await adminAPI.createRecord(createRecordForm);
      toast.success('Record created');
      setShowCreateRecordDialog(false);
      setCreateRecordForm({ user_id: '', name: '', record_type: 'A', content: '', ttl: 1, proxied: false, zone_id: zones.length > 0 ? zones[0].id : '' });
      fetchAllRecords(); fetchUsers();
    } catch (err) { setCreateRecordError(err.response?.data?.detail || 'Failed'); }
    finally { setCreateRecordLoading(false); }
  };

  // === Plan actions ===
  const openCreatePlan = () => {
    setEditingPlan(null);
    setPlanForm({ plan_id: '', name: '', name_fa: '', price: '', price_fa: '', record_limit: 0, features: '', features_fa: '', popular: false, sort_order: plans.length });
    setPlanFormError('');
    setShowPlanDialog(true);
  };

  const openEditPlan = (p) => {
    setEditingPlan(p);
    setPlanForm({
      plan_id: p.plan_id,
      name: p.name, name_fa: p.name_fa || '',
      price: p.price, price_fa: p.price_fa || '',
      record_limit: p.record_limit,
      features: (p.features || []).join('\n'),
      features_fa: (p.features_fa || []).join('\n'),
      popular: p.popular || false,
      sort_order: p.sort_order || 0,
    });
    setPlanFormError('');
    setShowPlanDialog(true);
  };

  const handleSavePlan = async () => {
    setPlanFormError('');
    setPlanFormLoading(true);
    const payload = {
      ...planForm,
      features: planForm.features.split('\n').filter(Boolean),
      features_fa: planForm.features_fa.split('\n').filter(Boolean),
    };
    try {
      if (editingPlan) {
        const { plan_id, ...rest } = payload;
        await adminAPI.updatePlan(editingPlan.plan_id, rest);
        toast.success(t('admin_plan_updated'));
      } else {
        await adminAPI.createPlan(payload);
        toast.success(t('admin_plan_created'));
      }
      setShowPlanDialog(false);
      fetchPlans();
    } catch (err) { setPlanFormError(err.response?.data?.detail || 'Failed'); }
    finally { setPlanFormLoading(false); }
  };

  const handleDeletePlan = async () => {
    if (!deletePlanId) return;
    try {
      await adminAPI.deletePlan(deletePlanId);
      toast.success(t('admin_plan_deleted'));
      setDeletePlanId(null);
      fetchPlans();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
  };

  // === Settings ===
  const handleSaveSettings = async () => {
    setSettingsSaving(true);
    try {
      await adminAPI.updateSettings(settings);
      toast.success(t('admin_settings_saved'));
    } catch { toast.error('Failed'); }
    finally { setSettingsSaving(false); }
  };

  // === Bot Management ===
  const handleSaveBotToken = async () => {
    setBotActionLoading('token');
    try {
      await adminAPI.updateBotToken(newBotToken);
      toast.success(t('admin_bot_token_updated'));
      setNewBotToken('');
      setShowTokenInput(false);
      setTimeout(() => fetchBotStatus(), 3000);
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
    finally { setBotActionLoading(''); }
  };

  const handleClearBotToken = async () => {
    setBotActionLoading('clear');
    try {
      await adminAPI.updateBotToken('');
      toast.success(t('admin_bot_stopped_msg'));
      setNewBotToken('');
      setShowTokenInput(false);
      setTimeout(() => fetchBotStatus(), 2000);
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
    finally { setBotActionLoading(''); }
  };

  const handleSaveAdminId = async () => {
    setBotActionLoading('admin');
    try {
      await adminAPI.updateBotAdminId(newAdminId);
      toast.success(t('admin_bot_admin_updated'));
      fetchBotStatus();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
    finally { setBotActionLoading(''); }
  };

  const handleStopBot = async () => {
    setBotActionLoading('stop');
    try {
      await adminAPI.stopBot();
      toast.success(t('admin_bot_stopped_msg'));
      setTimeout(() => fetchBotStatus(), 1000);
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
    finally { setBotActionLoading(''); }
  };

  const handleStartBot = async () => {
    setBotActionLoading('start');
    try {
      await adminAPI.startBot();
      toast.success(t('admin_bot_started'));
      setTimeout(() => fetchBotStatus(), 5000);
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
    finally { setBotActionLoading(''); }
  };

  // === Zones ===
  const handleAddZone = async () => {
    if (!newZoneId.trim()) return;
    setAddZoneLoading(true);
    try {
      await adminAPI.addZone(newZoneId.trim(), newZoneToken.trim());
      toast.success(t('admin_zone_added'));
      setNewZoneId('');
      setNewZoneToken('');
      setShowAddZone(false);
      fetchZones();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed to add zone'); }
    finally { setAddZoneLoading(false); }
  };

  const handleRemoveZone = async (zoneId) => {
    try {
      await adminAPI.removeZone(zoneId);
      toast.success(t('admin_zone_removed'));
      fetchZones();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
  };

  const handleToggleZone = async (zoneId, currentStatus) => {
    const newEnabled = currentStatus !== 'active';
    try {
      await adminAPI.toggleZone(zoneId, newEnabled);
      toast.success(newEnabled ? t('admin_zone_enabled_msg') : t('admin_zone_disabled_msg'));
      fetchZones();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
  };

  const handleUpdateCfToken = async () => {
    if (!newCfToken.trim()) return;
    setCfTokenLoading(true);
    try {
      const res = await adminAPI.updateCfToken(newCfToken.trim());
      toast.success(t('admin_cf_api_token_updated'));
      setCfTokenInfo({ has_token: true, masked_token: res.data.masked_token });
      setNewCfToken('');
      setShowCfTokenInput(false);
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
    finally { setCfTokenLoading(false); }
  };

  const handleTestCfToken = async () => {
    setCfTestLoading(true);
    setCfTestResult(null);
    try {
      const res = await adminAPI.testCfToken();
      setCfTestResult(res.data);
      if (res.data.success) {
        toast.success(t('admin_cf_api_token_valid'));
      } else {
        toast.error(res.data.message || t('admin_cf_api_token_invalid'));
      }
    } catch {
      setCfTestResult({ success: false, message: 'Connection failed' });
      toast.error(t('admin_cf_api_token_invalid'));
    }
    finally { setCfTestLoading(false); }
  };

  const handleSaveBackupSettings = async (fields) => {
    setBackupLoading(true);
    try {
      await adminAPI.updateBackupSettings(fields);
      toast.success(lang === 'fa' ? 'تنظیمات ذخیره شد' : 'Settings saved');
      fetchBackupSettings();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
    finally { setBackupLoading(false); }
  };

  const handleBackupNow = async () => {
    setBackupNowLoading(true);
    try {
      await adminAPI.triggerBackup();
      toast.success(t('admin_backup_success'));
      fetchBackupSettings();
    } catch (err) { toast.error(err.response?.data?.detail || 'Backup failed'); }
    finally { setBackupNowLoading(false); }
  };

  const handleRestore = async () => {
    if (!window.confirm(lang === 'fa' ? 'آیا مطمئنید؟ دیتابیس فعلی جایگزین میشه!' : 'Are you sure? Current database will be replaced!')) return;
    setBackupRestoreLoading(true);
    try {
      await adminAPI.restoreBackup();
      toast.success(t('admin_backup_restore_success'));
      // The database was just replaced — everything on screen is stale.
      fetchUsers(); fetchAllRecords(); fetchPlans(); fetchSettings();
      fetchAdminLogs(); fetchZones(); fetchBackupSettings();
    } catch (err) { toast.error(err.response?.data?.detail || 'Restore failed'); }
    finally { setBackupRestoreLoading(false); }
  };

  const handleTestBackupBot = async () => {
    const token = backupBotToken || (backupSettings.bot_token_set ? '__stored__' : '');
    const adminId = backupSettings.admin_id;
    if (!adminId) { toast.error(lang === 'fa' ? 'آیدی ادمین وارد نشده' : 'Admin ID is required'); return; }
    setBackupTestLoading(true);
    try {
      const body = { admin_id: adminId };
      if (backupBotToken) body.bot_token = backupBotToken;
      else {
        // Use stored token - fetch from settings
        const sRes = await adminAPI.getBackupSettings();
        if (!sRes.data.bot_token_set) { toast.error(lang === 'fa' ? 'توکن ربات تنظیم نشده' : 'Bot token not set'); setBackupTestLoading(false); return; }
        // We need the actual token - send request without it, backend will use stored
      }
      const res = await adminAPI.testBackupBot(body);
      if (res.data.success) toast.success(t('admin_backup_test_success'));
      else toast.error(res.data.message);
    } catch (err) { toast.error(err.response?.data?.detail || 'Test failed'); }
    finally { setBackupTestLoading(false); }
  };

  // === SMTP ===
  const handleSaveSmtp = async () => {
    setSmtpSaving(true);
    try {
      await adminAPI.updateSmtp(newSmtpEmail, newSmtpPassword);
      toast.success(t('admin_smtp_saved'));
      setNewSmtpPassword('');
      fetchSmtpStatus();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
    finally { setSmtpSaving(false); }
  };

  const handleToggleVerification = async () => {
    try {
      const newState = !smtpStatus.email_verification_enabled;
      await adminAPI.toggleVerification(newState);
      setSmtpStatus(prev => ({ ...prev, email_verification_enabled: newState }));
      toast.success(newState ? t('admin_verification_on') : t('admin_verification_off'));
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
  };

  const planColors = {
    free: 'bg-muted text-muted-foreground',
    pro: 'bg-primary/10 text-primary border-primary/20',
    enterprise: 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 border-yellow-500/20',
  };
  const typeColors = {
    A: 'bg-primary/10 text-primary border-primary/20',
    AAAA: 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/20',
    CNAME: 'bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20',
  };
  const nonAdminUsers = users.filter(u => u.role !== 'admin');

  return (
    <div className="min-h-screen page-mount" data-testid="admin-page">
      <div className="max-w-7xl mx-auto px-4 py-8 md:py-12">
        {/* Header */}
        <div className="flex items-center justify-between gap-3 mb-8 pb-6 border-b border-border flex-wrap relative">
          <div className="absolute inset-x-0 -bottom-px h-px bg-gradient-to-r from-primary/60 via-transparent to-transparent"></div>
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 border border-primary/40 bg-primary/10 flex items-center justify-center bp-frame">
              <span className="bp-c-tr" /><span className="bp-c-bl" />
              <Crown className="w-5 h-5 text-primary" />
            </div>
            <div>
              <span className="editorial-mark">{lang === 'fa' ? 'پنل مدیریت' : 'ADMIN PANEL'}</span>
              <h1 className="text-3xl md:text-4xl font-display font-semibold tracking-tighter mt-2" data-testid="admin-title">
                {t('admin_title')}
              </h1>
              <p className="text-sm text-muted-foreground mt-2">
                {lang === 'fa' ? 'ورود به‌عنوان ' : 'Signed in as '}
                <span className="text-foreground font-medium">{user?.name || user?.email}</span>
              </p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-primary/40 text-primary font-mono text-[10px] uppercase tracking-widest bg-primary/5">
            <span className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse" /> SUPERUSER · ROOT
          </span>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-border border border-border mb-8 bp-frame">
          <span className="bp-c-tr" /><span className="bp-c-bl" />
          <div className="bg-card p-6 hover:bg-muted/30 transition-colors group" data-testid="admin-stat-users">
            <div className="flex items-center justify-between mb-3">
              <span className="mono-label">USERS · 01</span>
              <Users className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
            </div>
            <p className="stat-numeral">{users.length}</p>
            <p className="text-[11px] text-muted-foreground font-mono mt-2 tracking-widest uppercase">{t('admin_total_users')}</p>
          </div>
          <div className="bg-card p-6 hover:bg-muted/30 transition-colors group" data-testid="admin-stat-records">
            <div className="flex items-center justify-between mb-3">
              <span className="mono-label">RECORDS · 02</span>
              <Server className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
            </div>
            <p className="stat-numeral">{allRecords.length}</p>
            <p className="text-[11px] text-muted-foreground font-mono mt-2 tracking-widest uppercase">{t('admin_total_records')}</p>
          </div>
          <div className="bg-card p-6 hover:bg-muted/30 transition-colors group" data-testid="admin-stat-plans">
            <div className="flex items-center justify-between mb-3">
              <span className="mono-label">PLANS · 03</span>
              <CreditCard className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
            </div>
            <p className="stat-numeral">{plans.length}</p>
            <p className="text-[11px] text-muted-foreground font-mono mt-2 tracking-widest uppercase">{t('admin_plans_tab')}</p>
          </div>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid grid-cols-5 w-full max-w-2xl rounded-none border border-border bg-card p-1 h-auto">
            <TabsTrigger value="users" data-testid="admin-tab-users" className="rounded-none data-[state=active]:bg-primary data-[state=active]:text-primary-foreground font-mono uppercase tracking-widest text-[11px]">
              <Users className="w-3.5 h-3.5 me-1.5" />{t('admin_users')}
            </TabsTrigger>
            <TabsTrigger value="records" data-testid="admin-tab-records" className="rounded-none data-[state=active]:bg-primary data-[state=active]:text-primary-foreground font-mono uppercase tracking-widest text-[11px]">
              <Server className="w-3.5 h-3.5 me-1.5" />{t('admin_records')}
            </TabsTrigger>
            <TabsTrigger value="plans" data-testid="admin-tab-plans" className="rounded-none data-[state=active]:bg-primary data-[state=active]:text-primary-foreground font-mono uppercase tracking-widest text-[11px]">
              <CreditCard className="w-3.5 h-3.5 me-1.5" />{t('admin_plans_tab')}
            </TabsTrigger>
            <TabsTrigger value="logs" data-testid="admin-tab-logs" className="rounded-none data-[state=active]:bg-primary data-[state=active]:text-primary-foreground font-mono uppercase tracking-widest text-[11px]">
              <Clock className="w-3.5 h-3.5 me-1.5" />{lang === 'fa' ? 'لاگ' : 'Logs'}
            </TabsTrigger>
            <TabsTrigger value="settings" data-testid="admin-tab-settings" className="rounded-none data-[state=active]:bg-primary data-[state=active]:text-primary-foreground font-mono uppercase tracking-widest text-[11px]">
              <Settings className="w-3.5 h-3.5 me-1.5" />{t('admin_settings')}
            </TabsTrigger>
          </TabsList>

          {/* ===== USERS TAB ===== */}
          <TabsContent value="users" className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-semibold">{t('admin_users')}</h2>
              <Button variant="ghost" size="sm" onClick={fetchUsers} data-testid="admin-refresh-users"><RefreshCw className="w-4 h-4" /></Button>
            </div>

            {/* Bulk Action Bar */}
            {selectedUserIds.size > 0 && (
              <div className="flex items-center gap-3 p-3 rounded-sm border border-primary/30 bg-primary/5 animate-fade-in" data-testid="bulk-action-bar">
                <Badge variant="default" className="text-sm">
                  {selectedUserIds.size} {t('admin_selected')}
                </Badge>
                <div className="flex gap-2 ms-auto">
                  <Button size="sm" variant="outline" onClick={() => { setBulkPlan('free'); setShowBulkPlanDialog(true); }} data-testid="bulk-change-plan-btn">
                    <ArrowUpDown className="w-4 h-4 me-1.5" />{t('admin_bulk_change_plan')}
                  </Button>
                  <Button size="sm" variant="destructive" onClick={() => setShowBulkDeleteDialog(true)} data-testid="bulk-delete-btn">
                    <Trash2 className="w-4 h-4 me-1.5" />{t('admin_bulk_delete')}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setSelectedUserIds(new Set())} data-testid="bulk-clear-btn">
                    {t('cancel')}
                  </Button>
                </div>
              </div>
            )}

            <div className="rounded-sm border border-border bg-card overflow-hidden">
              {usersLoading ? (
                <div className="flex justify-center p-8"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
              ) : users.length === 0 ? (
                <div className="text-center p-8 text-muted-foreground">{t('admin_no_users')}</div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-12">
                          <Checkbox
                            checked={selectedUserIds.size > 0 && selectedUserIds.size === users.filter(u => u.role !== 'admin').length}
                            onCheckedChange={toggleSelectAll}
                            data-testid="select-all-checkbox"
                          />
                        </TableHead>
                        <TableHead>{lang === 'fa' ? 'نام' : 'Name'}</TableHead>
                        <TableHead>{lang === 'fa' ? 'ایمیل' : 'Email'}</TableHead>
                        <TableHead>{lang === 'fa' ? 'پلن' : 'Plan'}</TableHead>
                        <TableHead>{lang === 'fa' ? 'نقش' : 'Role'}</TableHead>
                        <TableHead>{lang === 'fa' ? 'رکوردها' : 'Records'}</TableHead>
                        <TableHead className="text-end">{t('table_actions')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {users.map((u) => (
                        <TableRow
                          key={u.id}
                          className={selectedUserIds.has(u.id) ? 'bg-primary/5' : ''}
                          data-testid={`admin-user-row-${u.id}`}
                        >
                          <TableCell>
                            {u.role !== 'admin' ? (
                              <Checkbox
                                checked={selectedUserIds.has(u.id)}
                                onCheckedChange={() => toggleUserSelection(u.id)}
                                data-testid={`select-user-${u.id}`}
                              />
                            ) : <div className="w-4" />}
                          </TableCell>
                          <TableCell className="font-medium">{u.name}</TableCell>
                          <TableCell className="font-mono text-sm">{u.email}</TableCell>
                          <TableCell>
                            <Badge variant="outline" className={planColors[u.plan] || 'bg-muted text-muted-foreground'}>{u.plan}</Badge>
                          </TableCell>
                          <TableCell>
                            <Badge variant={u.role === 'admin' ? 'default' : 'secondary'}>{u.role || 'user'}</Badge>
                          </TableCell>
                          <TableCell>{u.record_count}/{u.record_limit === 0 ? (lang === 'fa' ? '∞' : '∞') : u.record_limit}</TableCell>
                          <TableCell className="text-end">
                            <div className="flex items-center justify-end gap-1">
                              <Button variant="ghost" size="sm" onClick={() => handleViewUserRecords(u)} title={t('admin_view_records')} data-testid={`admin-view-records-${u.id}`}>
                                <Eye className="w-4 h-4" />
                              </Button>
                              {u.role !== 'admin' && (
                                <>
                                  <Button variant="ghost" size="sm" onClick={() => { setPlanDialogUser(u); setSelectedPlan(u.plan); }} title={t('admin_change_plan')} data-testid={`admin-change-plan-${u.id}`}>
                                    <ArrowUpDown className="w-4 h-4" />
                                  </Button>
                                  <Button variant="ghost" size="sm" onClick={() => { setPasswordDialogUser(u); setNewPassword(''); }} title={t('admin_change_password')} data-testid={`admin-change-pw-${u.id}`}>
                                    <KeyRound className="w-4 h-4" />
                                  </Button>
                                  <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => setDeleteUserId(u.id)} title={t('admin_delete_user')} data-testid={`admin-delete-user-${u.id}`}>
                                    <Trash2 className="w-4 h-4" />
                                  </Button>
                                </>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </div>
          </TabsContent>

          {/* ===== RECORDS TAB ===== */}
          <TabsContent value="records" className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-semibold">{t('admin_records')}</h2>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={allRecords.length === 0} onClick={async () => {
                  try {
                    const res = await adminAPI.exportAllRecordsCSV();
                    downloadBlob(res.data, `all-dns-records-${fileTimestamp()}.csv`);
                  } catch (err) { toast.error(err.response?.data?.detail || 'Export failed'); }
                }} data-testid="admin-export-records-btn">
                  <Download className="w-4 h-4 me-2" />{t('export_csv')}
                </Button>
                <Button size="sm" variant="outline" onClick={() => { setAdminImportCsvText(''); setAdminImportResult(null); setShowAdminImportDialog(true); }} data-testid="admin-import-records-btn">
                  <Upload className="w-4 h-4 me-2" />{t('import_csv')}
                </Button>
                <Button size="sm" onClick={() => { setCreateRecordForm(p => ({ ...p, zone_id: zones.length > 0 ? zones[0].id : '' })); setShowCreateRecordDialog(true); }} data-testid="admin-add-record-btn">
                  <Plus className="w-4 h-4 me-2" />{t('admin_add_record')}
                </Button>
                <Button variant="ghost" size="sm" onClick={fetchAllRecords} data-testid="admin-refresh-records"><RefreshCw className="w-4 h-4" /></Button>
              </div>
            </div>
            <div className="rounded-sm border border-border bg-card overflow-hidden">
              {recordsLoading ? (
                <div className="flex justify-center p-8"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
              ) : allRecords.length === 0 ? (
                <div className="text-center p-8 text-muted-foreground">{t('admin_no_records')}</div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('table_type')}</TableHead>
                        <TableHead>{t('table_name')}</TableHead>
                        <TableHead>{t('table_content')}</TableHead>
                        <TableHead>{lang === 'fa' ? 'کاربر' : 'User'}</TableHead>
                        <TableHead className="text-end">{t('table_actions')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {allRecords.map((rec) => (
                        <TableRow key={rec.id} data-testid={`admin-record-row-${rec.id}`}>
                          <TableCell><Badge variant="outline" className={typeColors[rec.record_type] || ''}>{rec.record_type}</Badge></TableCell>
                          <TableCell className="font-mono text-sm">{rec.full_name}</TableCell>
                          <TableCell className="font-mono text-sm max-w-[180px] truncate">{rec.content}</TableCell>
                          <TableCell className="text-sm">{rec.user_email || rec.user_id}</TableCell>
                          <TableCell className="text-end">
                            <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => setDeleteRecordId(rec.id)} data-testid={`admin-delete-record-${rec.id}`}>
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </div>
          </TabsContent>

          {/* ===== PLANS TAB ===== */}
          <TabsContent value="plans" className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-semibold">{t('admin_plans_tab')}</h2>
              <div className="flex gap-2">
                <Button size="sm" onClick={openCreatePlan} data-testid="admin-add-plan-btn">
                  <Plus className="w-4 h-4 me-2" />{t('admin_add_plan')}
                </Button>
                <Button variant="ghost" size="sm" onClick={fetchPlans} data-testid="admin-refresh-plans"><RefreshCw className="w-4 h-4" /></Button>
              </div>
            </div>
            <div className="rounded-sm border border-border bg-card overflow-hidden">
              {plansLoading ? (
                <div className="flex justify-center p-8"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
              ) : plans.length === 0 ? (
                <div className="text-center p-8 text-muted-foreground">{t('admin_no_plans')}</div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>ID</TableHead>
                        <TableHead>{lang === 'fa' ? 'نام' : 'Name'}</TableHead>
                        <TableHead>{t('admin_plan_price')}</TableHead>
                        <TableHead>{t('admin_plan_limit')}</TableHead>
                        <TableHead>{t('admin_plan_popular')}</TableHead>
                        <TableHead>{lang === 'fa' ? 'ترتیب' : 'Order'}</TableHead>
                        <TableHead className="text-end">{t('table_actions')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {plans.map((p) => (
                        <TableRow key={p.plan_id} data-testid={`admin-plan-row-${p.plan_id}`}>
                          <TableCell className="font-mono text-sm">{p.plan_id}</TableCell>
                          <TableCell>
                            <div>{p.name}</div>
                            <div className="text-xs text-muted-foreground">{p.name_fa}</div>
                          </TableCell>
                          <TableCell>
                            <div>{p.price}</div>
                            <div className="text-xs text-muted-foreground">{p.price_fa}</div>
                          </TableCell>
                          <TableCell className="font-semibold">{p.record_limit === 0 ? (lang === 'fa' ? 'نامحدود' : 'Unlimited') : p.record_limit}</TableCell>
                          <TableCell>
                            {p.popular ? <Badge className="bg-primary/10 text-primary">{lang === 'fa' ? 'بله' : 'Yes'}</Badge> : <span className="text-muted-foreground text-sm">{lang === 'fa' ? 'خیر' : 'No'}</span>}
                          </TableCell>
                          <TableCell>{p.sort_order}</TableCell>
                          <TableCell className="text-end">
                            <div className="flex items-center justify-end gap-1">
                              <Button variant="ghost" size="sm" onClick={() => openEditPlan(p)} data-testid={`admin-edit-plan-${p.plan_id}`}>
                                <Pencil className="w-4 h-4" />
                              </Button>
                              <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => setDeletePlanId(p.plan_id)} data-testid={`admin-delete-plan-${p.plan_id}`}>
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </div>
          </TabsContent>

          {/* ===== ACTIVITY LOGS TAB ===== */}
          <TabsContent value="logs" className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Clock className="w-5 h-5" />
                {lang === 'fa' ? 'لاگ فعالیت‌ها' : 'Activity Logs'}
              </h2>
              <div className="flex items-center gap-2">
                <select
                  className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                  value={adminLogFilter}
                  onChange={(e) => { setAdminLogFilter(e.target.value); fetchAdminLogs(1, e.target.value); }}
                >
                  <option value="">{lang === 'fa' ? 'همه فعالیت‌ها' : 'All Actions'}</option>
                  <option value="login">{lang === 'fa' ? 'ورود' : 'Login'}</option>
                  <option value="register">{lang === 'fa' ? 'ثبت‌نام' : 'Register'}</option>
                  <option value="record_created">{lang === 'fa' ? 'ساخت رکورد' : 'Record Created'}</option>
                  <option value="record_updated">{lang === 'fa' ? 'ویرایش رکورد' : 'Record Updated'}</option>
                  <option value="record_deleted">{lang === 'fa' ? 'حذف رکورد' : 'Record Deleted'}</option>
                  <option value="telegram_linked">{lang === 'fa' ? 'اتصال تلگرام' : 'Telegram Linked'}</option>
                </select>
                <Button variant="ghost" size="sm" onClick={() => fetchAdminLogs(1, adminLogFilter)}>
                  <RefreshCw className="w-4 h-4" />
                </Button>
              </div>
            </div>

            <div className="rounded-sm border border-border bg-card overflow-hidden">
              {adminLogLoading ? (
                <div className="flex items-center justify-center p-12">
                  <Loader2 className="w-6 h-6 animate-spin text-primary" />
                </div>
              ) : adminLogs.length === 0 ? (
                <div className="text-center p-12 text-muted-foreground">
                  {lang === 'fa' ? 'هنوز فعالیتی ثبت نشده.' : 'No activity logs yet.'}
                </div>
              ) : (
                <>
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>{lang === 'fa' ? 'کاربر' : 'User'}</TableHead>
                          <TableHead>{lang === 'fa' ? 'فعالیت' : 'Action'}</TableHead>
                          <TableHead>{lang === 'fa' ? 'جزئیات' : 'Details'}</TableHead>
                          <TableHead>{lang === 'fa' ? 'تاریخ' : 'Date'}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {adminLogs.map((log) => (
                          <TableRow key={log.id}>
                            <TableCell className="font-medium text-sm">{log.user_email}</TableCell>
                            <TableCell>
                              <Badge variant={
                                log.action === 'record_created' ? 'default' :
                                log.action === 'record_deleted' ? 'destructive' :
                                log.action === 'record_updated' ? 'secondary' :
                                'outline'
                              } className="text-xs">
                                {log.action === 'record_created' ? (lang === 'fa' ? 'ساخت رکورد' : 'Created') :
                                 log.action === 'record_deleted' ? (lang === 'fa' ? 'حذف رکورد' : 'Deleted') :
                                 log.action === 'record_updated' ? (lang === 'fa' ? 'ویرایش رکورد' : 'Updated') :
                                 log.action === 'login' ? (lang === 'fa' ? 'ورود' : 'Login') :
                                 log.action === 'register' ? (lang === 'fa' ? 'ثبت‌نام' : 'Register') :
                                 log.action === 'telegram_linked' ? (lang === 'fa' ? 'تلگرام' : 'Telegram') :
                                 log.action}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground font-mono max-w-xs truncate">{log.details || '—'}</TableCell>
                            <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                              {new Date(log.created_at).toLocaleDateString(lang === 'fa' ? 'fa-IR' : 'en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                  {adminLogPages > 1 && (
                    <div className="flex items-center justify-center gap-2 p-3 border-t border-border">
                      <Button variant="ghost" size="sm" disabled={adminLogPage <= 1} onClick={() => fetchAdminLogs(adminLogPage - 1, adminLogFilter)}>
                        <ChevronLeft className="w-4 h-4 me-1" />{lang === 'fa' ? 'قبلی' : 'Prev'}
                      </Button>
                      <span className="text-xs text-muted-foreground">{adminLogPage}/{adminLogPages}</span>
                      <Button variant="ghost" size="sm" disabled={adminLogPage >= adminLogPages} onClick={() => fetchAdminLogs(adminLogPage + 1, adminLogFilter)}>
                        {lang === 'fa' ? 'بعدی' : 'Next'}<ChevronRight className="w-4 h-4 ms-1" />
                      </Button>
                    </div>
                  )}
                </>
              )}
            </div>
          </TabsContent>

          {/* ===== SETTINGS TAB ===== */}
          <TabsContent value="settings" className="space-y-6">
            <h2 className="text-xl font-semibold">{t('admin_settings')}</h2>

            {/* ── Telegram Bot Management ── */}
            <div className="rounded-sm border border-border bg-card p-6 space-y-5">
              <div className="flex items-center gap-3 mb-2">
                <Bot className="w-5 h-5 text-primary" />
                <h3 className="text-lg font-semibold">{t('admin_bot_management')}</h3>
                <Button variant="ghost" size="sm" onClick={fetchBotStatus} disabled={botLoading}>
                  <RefreshCw className={`w-4 h-4 ${botLoading ? 'animate-spin' : ''}`} />
                </Button>
              </div>

              {botLoading ? (
                <div className="flex justify-center p-4"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
              ) : (
                <div className="space-y-4">
                  {/* Status */}
                  <div className="flex items-center gap-3 flex-wrap">
                    <Label className="min-w-[100px]">{t('admin_bot_status')}:</Label>
                    {botStatus.bot_running ? (
                      <Badge className="bg-green-500/10 text-green-600 border-green-500/20">
                        ● {t('admin_bot_running')}
                      </Badge>
                    ) : botStatus.has_token ? (
                      <Badge variant="outline" className="text-yellow-600 border-yellow-500/30">
                        ○ {t('admin_bot_stopped')}
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-muted-foreground">
                        ○ {t('admin_bot_no_token')}
                      </Badge>
                    )}
                    {botStatus.bot_username && (
                      <span className="text-sm text-muted-foreground">{botStatus.bot_username}</span>
                    )}
                  </div>

                  {/* Token */}
                  <div className="space-y-2">
                    <Label>{t('admin_bot_token')}</Label>
                    {botStatus.has_token && !showTokenInput ? (
                      <div className="flex items-center gap-2 flex-wrap">
                        <code className="text-sm bg-muted px-3 py-1.5 rounded font-mono">{botStatus.masked_token}</code>
                        <Button variant="outline" size="sm" onClick={() => setShowTokenInput(true)}>
                          <Pencil className="w-3 h-3 me-1" /> {lang === 'fa' ? 'تغییر' : 'Change'}
                        </Button>
                        <Button variant="outline" size="sm" className="text-destructive hover:text-destructive" onClick={handleClearBotToken} disabled={botActionLoading === 'clear'}>
                          {botActionLoading === 'clear' ? <Loader2 className="w-3 h-3 animate-spin me-1" /> : <Trash2 className="w-3 h-3 me-1" />}
                          {t('admin_bot_clear_token')}
                        </Button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <Input
                          value={newBotToken}
                          onChange={(e) => setNewBotToken(e.target.value)}
                          placeholder={t('admin_bot_token_placeholder')}
                          className="font-mono max-w-md"
                          dir="ltr"
                        />
                        <Button size="sm" onClick={handleSaveBotToken} disabled={botActionLoading === 'token' || !newBotToken.trim()}>
                          {botActionLoading === 'token' ? <Loader2 className="w-4 h-4 animate-spin me-1" /> : <Save className="w-4 h-4 me-1" />}
                          {t('admin_bot_save_token')}
                        </Button>
                        {showTokenInput && (
                          <Button variant="ghost" size="sm" onClick={() => { setShowTokenInput(false); setNewBotToken(''); }}>
                            <X className="w-4 h-4" />
                          </Button>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Admin ID */}
                  <div className="space-y-2">
                    <Label>{t('admin_bot_admin_id')}</Label>
                    <div className="flex items-center gap-2">
                      <Input
                        value={newAdminId}
                        onChange={(e) => setNewAdminId(e.target.value)}
                        placeholder={t('admin_bot_admin_id_placeholder')}
                        className="max-w-[250px] font-mono"
                        dir="ltr"
                      />
                      <Button size="sm" onClick={handleSaveAdminId} disabled={botActionLoading === 'admin'}>
                        {botActionLoading === 'admin' ? <Loader2 className="w-4 h-4 animate-spin me-1" /> : <Save className="w-4 h-4 me-1" />}
                        {t('admin_bot_save_admin')}
                      </Button>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {lang === 'fa' ? 'آیدی عددی تلگرام ادمین (از @userinfobot بگیرید)' : 'Numeric Telegram ID (get from @userinfobot)'}
                    </p>
                  </div>

                  {/* Start/Stop */}
                  {botStatus.has_token && (
                    <div className="flex gap-2 pt-2 border-t border-border">
                      {botStatus.bot_running ? (
                        <>
                          <Button variant="outline" className="text-destructive hover:text-destructive" onClick={handleStopBot} disabled={!!botActionLoading}>
                            {botActionLoading === 'stop' ? <Loader2 className="w-4 h-4 animate-spin me-1" /> : <Square className="w-4 h-4 me-1" />}
                            {t('admin_bot_stop')}
                          </Button>
                          <Button variant="outline" onClick={handleStartBot} disabled={!!botActionLoading}>
                            {botActionLoading === 'start' ? <Loader2 className="w-4 h-4 animate-spin me-1" /> : <RefreshCw className="w-4 h-4 me-1" />}
                            {t('admin_bot_restart')}
                          </Button>
                        </>
                      ) : (
                        <Button onClick={handleStartBot} disabled={!!botActionLoading}>
                          {botActionLoading === 'start' ? <Loader2 className="w-4 h-4 animate-spin me-1" /> : <Play className="w-4 h-4 me-1" />}
                          {t('admin_bot_start')}
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* ── Cloudflare API Token ── */}
            <div className="rounded-sm border border-border bg-card p-6 space-y-4">
              <div className="flex items-center gap-3">
                <KeyRound className="w-5 h-5 text-primary" />
                <h3 className="text-lg font-semibold">{t('admin_cf_api_token')}</h3>
              </div>
              <div className="flex items-center gap-3 flex-wrap">
                <Label className="min-w-[100px]">{t('admin_cf_api_token_current')}:</Label>
                {cfTokenInfo.has_token ? (
                  <code className="text-sm bg-muted px-3 py-1.5 rounded font-mono">{cfTokenInfo.masked_token}</code>
                ) : (
                  <span className="text-sm text-muted-foreground">{lang === 'fa' ? 'تنظیم نشده' : 'Not set'}</span>
                )}
              </div>
              {!showCfTokenInput ? (
                <div className="flex items-center gap-2 flex-wrap">
                  <Button size="sm" variant="outline" onClick={() => setShowCfTokenInput(true)} data-testid="admin-cf-token-edit-btn">
                    <Pencil className="w-4 h-4 me-1" /> {t('admin_cf_api_token_update')}
                  </Button>
                  {cfTokenInfo.has_token && (
                    <Button size="sm" variant="outline" onClick={handleTestCfToken} disabled={cfTestLoading} data-testid="admin-cf-token-test-btn">
                      {cfTestLoading ? <Loader2 className="w-4 h-4 animate-spin me-1" /> : <Zap className="w-4 h-4 me-1" />}
                      {cfTestLoading ? t('admin_cf_api_token_testing') : t('admin_cf_api_token_test')}
                    </Button>
                  )}
                  {cfTestResult && (
                    <span className={`inline-flex items-center gap-1 text-sm ${cfTestResult.success ? 'text-green-600' : 'text-destructive'}`}>
                      {cfTestResult.success ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                      {cfTestResult.success ? t('admin_cf_api_token_valid') : cfTestResult.message}
                    </span>
                  )}
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Input
                    type="password"
                    value={newCfToken}
                    onChange={(e) => setNewCfToken(e.target.value)}
                    placeholder={lang === 'fa' ? 'توکن جدید را وارد کنید...' : 'Enter new API token...'}
                    className="max-w-sm font-mono"
                    data-testid="admin-cf-token-input"
                  />
                  <Button size="sm" onClick={handleUpdateCfToken} disabled={cfTokenLoading || !newCfToken.trim()} data-testid="admin-cf-token-save-btn">
                    {cfTokenLoading ? <Loader2 className="w-4 h-4 animate-spin me-1" /> : <Save className="w-4 h-4 me-1" />}
                    {t('save')}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => { setShowCfTokenInput(false); setNewCfToken(''); }}>
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              )}
            </div>

            {/* ── Automatic Backup ── */}
            <div className="rounded-sm border border-border bg-card p-6 space-y-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Database className="w-5 h-5 text-primary" />
                  <div>
                    <h3 className="text-lg font-semibold">{t('admin_backup')}</h3>
                    <p className="text-sm text-muted-foreground">{t('admin_backup_desc')}</p>
                  </div>
                </div>
                <Button
                  variant={backupSettings.enabled ? "default" : "outline"}
                  size="sm"
                  onClick={() => handleSaveBackupSettings({ enabled: !backupSettings.enabled })}
                  disabled={backupLoading}
                  data-testid="admin-backup-toggle"
                >
                  {backupSettings.enabled ? <ToggleRight className="w-4 h-4 me-1" /> : <ToggleLeft className="w-4 h-4 me-1" />}
                  {backupSettings.enabled ? 'ON' : 'OFF'}
                </Button>
              </div>

              {/* Bot Token */}
              <div className="space-y-2">
                <Label>{t('admin_backup_bot_token')}</Label>
                {backupSettings.bot_token_set && (
                  <div className="flex items-center gap-1 mb-1">
                    <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
                    <code className="text-xs bg-muted px-2 py-0.5 rounded font-mono">{backupSettings.masked_token}</code>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <Input
                    type="password"
                    value={backupBotToken}
                    onChange={(e) => setBackupBotToken(e.target.value)}
                    placeholder={backupSettings.bot_token_set ? (lang === 'fa' ? 'توکن جدید (اختیاری)...' : 'New token (optional)...') : '123456789:ABCdefGHI...'}
                    className="max-w-md font-mono"
                    data-testid="admin-backup-token-input"
                  />
                  <Button size="sm" onClick={() => {
                    if (backupBotToken.trim()) {
                      handleSaveBackupSettings({ bot_token: backupBotToken.trim() });
                      setBackupBotToken('');
                    }
                  }} disabled={!backupBotToken.trim() || backupLoading} data-testid="admin-backup-token-save">
                    {backupLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  </Button>
                </div>
              </div>

              {/* Admin ID */}
              <div className="space-y-2">
                <Label>{t('admin_backup_admin_id')}</Label>
                <div className="flex items-center gap-2">
                  <Input
                    value={backupSettings.admin_id}
                    onChange={(e) => setBackupSettings(p => ({ ...p, admin_id: e.target.value }))}
                    placeholder="123456789"
                    className="max-w-[200px] font-mono"
                    data-testid="admin-backup-admin-id"
                  />
                  <Button size="sm" variant="outline" onClick={() => handleSaveBackupSettings({ admin_id: backupSettings.admin_id })} disabled={backupLoading}>
                    <Save className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              {/* Interval */}
              <div className="space-y-2">
                <Label>{t('admin_backup_interval')}</Label>
                <div className="flex items-center gap-2">
                  <Select
                    value={String(backupSettings.interval_minutes)}
                    onValueChange={(v) => {
                      setBackupSettings(p => ({ ...p, interval_minutes: parseInt(v) }));
                      handleSaveBackupSettings({ interval_minutes: parseInt(v) });
                    }}
                  >
                    <SelectTrigger className="w-[200px]" data-testid="admin-backup-interval">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="30">30 {t('admin_backup_minutes')}</SelectItem>
                      <SelectItem value="60">1 {t('admin_backup_hours')}</SelectItem>
                      <SelectItem value="180">3 {t('admin_backup_hours')}</SelectItem>
                      <SelectItem value="360">6 {t('admin_backup_hours')}</SelectItem>
                      <SelectItem value="720">12 {t('admin_backup_hours')}</SelectItem>
                      <SelectItem value="1440">24 {t('admin_backup_hours')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Last backup info */}
              {backupSettings.last_backup && (
                <div className="text-sm text-muted-foreground">
                  {t('admin_backup_last')}: {new Date(backupSettings.last_backup).toLocaleString(lang === 'fa' ? 'fa-IR' : 'en')}
                  {backupSettings.last_backup_size && ` (${(backupSettings.last_backup_size / 1024).toFixed(1)} KB)`}
                </div>
              )}

              {/* Action buttons */}
              <div className="flex items-center gap-2 flex-wrap pt-2 border-t border-border">
                <Button size="sm" variant="outline" onClick={handleTestBackupBot} disabled={backupTestLoading || (!backupSettings.bot_token_set && !backupBotToken)} data-testid="admin-backup-test-btn">
                  {backupTestLoading ? <Loader2 className="w-4 h-4 animate-spin me-1" /> : <Zap className="w-4 h-4 me-1" />}
                  {t('admin_backup_test')}
                </Button>
                <Button size="sm" onClick={handleBackupNow} disabled={backupNowLoading || !backupSettings.bot_token_set} data-testid="admin-backup-now-btn">
                  {backupNowLoading ? <Loader2 className="w-4 h-4 animate-spin me-1" /> : <Upload className="w-4 h-4 me-1" />}
                  {backupNowLoading ? t('admin_backup_running') : t('admin_backup_now')}
                </Button>
                <Button size="sm" variant="outline" className="text-destructive hover:text-destructive" onClick={handleRestore} disabled={backupRestoreLoading || !backupSettings.bot_token_set} data-testid="admin-backup-restore-btn">
                  {backupRestoreLoading ? <Loader2 className="w-4 h-4 animate-spin me-1" /> : <Download className="w-4 h-4 me-1" />}
                  {backupRestoreLoading ? t('admin_backup_restoring') : t('admin_backup_restore')}
                </Button>
              </div>
            </div>

            {/* ── Cloudflare Zones ── */}
            <div className="rounded-sm border border-border bg-card p-6 space-y-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Globe className="w-5 h-5 text-primary" />
                  <h3 className="text-lg font-semibold">{t('admin_zones')}</h3>
                  <Button variant="ghost" size="sm" onClick={fetchZones} disabled={zonesLoading}>
                    <RefreshCw className={`w-4 h-4 ${zonesLoading ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
                <Button size="sm" variant="outline" onClick={() => setShowAddZone(!showAddZone)}>
                  <Plus className="w-4 h-4 me-1" /> {t('admin_add_zone')}
                </Button>
              </div>

              {/* Add Zone Form */}
              {showAddZone && (
                <div className="rounded-lg border border-dashed border-primary/30 bg-primary/5 p-4 space-y-3">
                  <div className="space-y-2">
                    <Label>{t('admin_zone_id')}</Label>
                    <Input
                      value={newZoneId}
                      onChange={(e) => setNewZoneId(e.target.value)}
                      placeholder={t('admin_zone_id_placeholder')}
                      className="font-mono"
                      dir="ltr"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>{t('admin_zone_api_token')}</Label>
                    <Input
                      value={newZoneToken}
                      onChange={(e) => setNewZoneToken(e.target.value)}
                      placeholder="API Token"
                      className="font-mono"
                      dir="ltr"
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={handleAddZone} disabled={addZoneLoading || !newZoneId.trim()}>
                      {addZoneLoading ? <Loader2 className="w-4 h-4 animate-spin me-1" /> : <Plus className="w-4 h-4 me-1" />}
                      {t('admin_add_zone')}
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => { setShowAddZone(false); setNewZoneId(''); setNewZoneToken(''); }}>
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              )}

              {/* Zones List */}
              {zonesLoading ? (
                <div className="flex justify-center p-4"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
              ) : zones.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  {lang === 'fa' ? 'زونی ثبت نشده' : 'No zones configured'}
                </p>
              ) : (
                <div className="rounded-lg border border-border overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('admin_zone_domain')}</TableHead>
                        <TableHead>{t('admin_zone_id')}</TableHead>
                        <TableHead>{t('admin_zone_status')}</TableHead>                        <TableHead className="w-[80px]"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {zones.map((z) => (
                        <TableRow key={z.id} data-testid={`admin-zone-row-${z.id}`}>
                          <TableCell className="font-medium">
                            {z.domain}
                            {z.is_primary && (
                              <Badge className="ms-2 bg-primary/10 text-primary border-primary/20" variant="outline">
                                {t('admin_zone_primary')}
                              </Badge>
                            )}
                          </TableCell>
                          <TableCell>
                            <code className="text-xs bg-muted px-2 py-0.5 rounded font-mono">{z.id.substring(0, 12)}...</code>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Switch
                                checked={z.status === 'active'}
                                onCheckedChange={() => handleToggleZone(z.id, z.status)}
                                data-testid={`admin-zone-toggle-${z.id}`}
                              />
                              {z.status === 'active' ? (
                                <Badge className="bg-green-500/10 text-green-600 border-green-500/20" data-testid={`admin-zone-status-${z.id}`}>
                                  {t('admin_zone_active')}
                                </Badge>
                              ) : (
                                <Badge className="bg-muted text-muted-foreground border-border" data-testid={`admin-zone-status-${z.id}`}>
                                  {t('admin_zone_disabled')}
                                </Badge>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            {!z.is_primary && (
                              <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => handleRemoveZone(z.id)} data-testid={`admin-zone-remove-${z.id}`}>
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </div>

            {/* ── Email Signup Form Toggle ── */}
            <div className="rounded-sm border border-border bg-card p-6 space-y-4" data-testid="admin-email-signup-card">
              <div className="flex items-center gap-3 mb-2">
                <UserPlus className="w-5 h-5 text-primary" />
                <h3 className="text-lg font-semibold">
                  {lang === 'fa' ? 'فرم ثبت‌نام ایمیلی' : 'Email Signup Form'}
                </h3>
              </div>
              <p className="text-sm text-muted-foreground">
                {lang === 'fa'
                  ? 'اگه این رو خاموش کنی، فرم ثبت‌نام با ایمیل و رمز عبور توی صفحه ثبت‌نام مخفی می‌شه و فقط دکمه ورود با گوگل نمایش داده می‌شه. کاربران فعلی همچنان می‌تونن وارد بشن.'
                  : 'When disabled, the email & password signup form is hidden and users can only register via Google. Existing users can still log in normally.'}
              </p>
              <div className="flex items-center justify-between gap-4 pt-2 border-t border-border">
                <div>
                  <Label className="font-mono text-sm">
                    {lang === 'fa' ? 'وضعیت فعلی' : 'Current state'}:
                  </Label>
                  <Badge
                    variant="outline"
                    className={`ms-2 ${emailSignupEnabled ? 'border-green-500/30 text-green-600 bg-green-500/10' : 'border-orange-500/30 text-orange-600 bg-orange-500/10'}`}
                    data-testid="admin-email-signup-badge"
                  >
                    ● {emailSignupEnabled
                      ? (lang === 'fa' ? 'فعال' : 'Enabled')
                      : (lang === 'fa' ? 'غیرفعال (فقط گوگل)' : 'Disabled (Google only)')}
                  </Badge>
                </div>
                <Button
                  variant={emailSignupEnabled ? 'default' : 'outline'}
                  onClick={handleToggleEmailSignup}
                  disabled={emailSignupSaving}
                  data-testid="admin-email-signup-toggle"
                  className="font-mono lowercase"
                >
                  {emailSignupSaving ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : emailSignupEnabled ? (
                    <><ToggleRight className="w-4 h-4 me-1.5" /> {lang === 'fa' ? 'غیرفعال کن' : 'disable'}</>
                  ) : (
                    <><ToggleLeft className="w-4 h-4 me-1.5" /> {lang === 'fa' ? 'فعال کن' : 'enable'}</>
                  )}
                </Button>
              </div>
            </div>

            {/* ── Email Verification / SMTP ── */}
            <div className="rounded-sm border border-border bg-card p-6 space-y-5">
              <div className="flex items-center gap-3 mb-2">
                <Mail className="w-5 h-5 text-primary" />
                <h3 className="text-lg font-semibold">{t('admin_smtp')}</h3>
                <Button variant="ghost" size="sm" onClick={fetchSmtpStatus} disabled={smtpLoading}>
                  <RefreshCw className={`w-4 h-4 ${smtpLoading ? 'animate-spin' : ''}`} />
                </Button>
              </div>

              {smtpLoading ? (
                <div className="flex justify-center p-4"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
              ) : (
                <div className="space-y-4">
                  {/* Status */}
                  <div className="flex items-center gap-3 flex-wrap">
                    <Label className="min-w-[100px]">{t('admin_smtp_status')}:</Label>
                    {smtpStatus.has_smtp ? (
                      <Badge className="bg-green-500/10 text-green-600 border-green-500/20">
                        ● {t('admin_smtp_enabled')} ({smtpStatus.smtp_email})
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-muted-foreground">
                        ○ {t('admin_smtp_not_configured')}
                      </Badge>
                    )}
                  </div>

                  {/* Toggle verification */}
                  {smtpStatus.has_smtp && (
                    <div className="flex items-center gap-3">
                      <Label>{t('admin_verification_toggle')}:</Label>
                      <Button
                        variant={smtpStatus.email_verification_enabled ? "default" : "outline"}
                        size="sm"
                        onClick={handleToggleVerification}
                      >
                        {smtpStatus.email_verification_enabled ? (
                          <><ToggleRight className="w-4 h-4 me-1" /> {t('admin_verification_on')}</>
                        ) : (
                          <><ToggleLeft className="w-4 h-4 me-1" /> {t('admin_verification_off')}</>
                        )}
                      </Button>
                    </div>
                  )}

                  {/* SMTP Credentials */}
                  <div className="space-y-3 pt-2 border-t border-border">
                    <div className="space-y-2">
                      <Label>{t('admin_smtp_email')}</Label>
                      <Input
                        value={newSmtpEmail}
                        onChange={(e) => setNewSmtpEmail(e.target.value)}
                        placeholder="your-email@gmail.com"
                        className="max-w-md font-mono"
                        dir="ltr"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{t('admin_smtp_password')}</Label>
                      <Input
                        type="password"
                        value={newSmtpPassword}
                        onChange={(e) => setNewSmtpPassword(e.target.value)}
                        placeholder="xxxx xxxx xxxx xxxx"
                        className="max-w-md font-mono"
                        dir="ltr"
                      />
                      <p className="text-xs text-muted-foreground">
                        {lang === 'fa' ? 'از App Password گوگل استفاده کنید: myaccount.google.com/apppasswords' : 'Use Google App Password: myaccount.google.com/apppasswords'}
                      </p>
                    </div>
                    <Button size="sm" onClick={handleSaveSmtp} disabled={smtpSaving || (!newSmtpEmail && !newSmtpPassword)}>
                      {smtpSaving ? <Loader2 className="w-4 h-4 animate-spin me-1" /> : <Save className="w-4 h-4 me-1" />}
                      {t('admin_smtp_save')}
                    </Button>
                  </div>
                </div>
              )}
            </div>

            {/* ── Site Settings ── */}
            <div className="rounded-sm border border-border bg-card p-6 space-y-5 max-w-xl">
              <div className="flex items-center gap-3 mb-2">
                <Settings className="w-5 h-5 text-primary" />
                <h3 className="text-lg font-semibold">{t('admin_settings')}</h3>
              </div>
              {settingsLoading ? (
                <div className="flex justify-center p-8"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
              ) : (
                <>
                  <div className="space-y-2">
                    <Label>{t('admin_telegram_id')}</Label>
                    <div className="flex items-center gap-2">
                      <span className="text-muted-foreground">@</span>
                      <Input value={settings.telegram_id} onChange={(e) => {
                        const id = e.target.value.replace('@', '');
                        setSettings(p => ({ ...p, telegram_id: id, telegram_url: id ? `https://t.me/${id}` : '' }));
                      }} placeholder="username" data-testid="admin-telegram-id-input" />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label>{t('admin_telegram_url')}</Label>
                    <Input value={settings.telegram_url} onChange={(e) => setSettings(p => ({ ...p, telegram_url: e.target.value }))} placeholder="https://t.me/username" data-testid="admin-telegram-url-input" disabled className="text-muted-foreground" />
                  </div>
                  <div className="space-y-2">
                    <Label>{t('admin_contact_en')}</Label>
                    <Input value={settings.contact_message_en} onChange={(e) => setSettings(p => ({ ...p, contact_message_en: e.target.value }))} data-testid="admin-contact-en-input" />
                  </div>
                  <div className="space-y-2">
                    <Label>{t('admin_contact_fa')}</Label>
                    <Input value={settings.contact_message_fa} onChange={(e) => setSettings(p => ({ ...p, contact_message_fa: e.target.value }))} dir="rtl" data-testid="admin-contact-fa-input" />
                  </div>
                  <div className="pt-4 border-t border-border space-y-2">
                    <Label className="flex items-center gap-2">
                      <Gift className="w-4 h-4 text-primary" />
                      {t('admin_referral_bonus')}
                    </Label>
                    <Input
                      type="number"
                      min="0"
                      value={settings.referral_bonus_per_invite}
                      onChange={(e) => setSettings(p => ({ ...p, referral_bonus_per_invite: parseInt(e.target.value) || 0 }))}
                      className="max-w-[200px]"
                      data-testid="admin-referral-bonus-input"
                    />
                    <p className="text-xs text-muted-foreground">
                      {lang === 'fa'
                        ? 'تعداد رکوردهای اضافه‌ای که به ازای هر دعوت موفق به کاربر داده میشه'
                        : 'Number of bonus records given to the referrer for each successful invite'}
                    </p>
                  </div>
                  <Button onClick={handleSaveSettings} disabled={settingsSaving} data-testid="admin-save-settings-btn">
                    {settingsSaving ? <Loader2 className="w-4 h-4 animate-spin me-2" /> : <Save className="w-4 h-4 me-2" />}
                    {t('admin_save_settings')}
                  </Button>
                </>
              )}
            </div>

            {/* ── Google OAuth ── */}
            <div className="rounded-sm border border-border bg-card p-6 space-y-5" data-testid="admin-google-oauth-section">
              <div className="flex items-center gap-3 mb-2">
                <Lock className="w-5 h-5 text-primary" />
                <h3 className="text-lg font-semibold">{t('admin_google_oauth')}</h3>
                <Button variant="ghost" size="sm" onClick={fetchGoogleOAuth} data-testid="admin-google-oauth-refresh">
                  <RefreshCw className="w-4 h-4" />
                </Button>
              </div>

              <p className="text-xs text-muted-foreground -mt-2">
                {lang === 'fa'
                  ? 'برای فعال‌سازی ورود/ثبت‌نام با گوگل، Client ID و Client Secret رو از Google Cloud Console بگیرید و اینجا وارد کنید.'
                  : 'Enter the Google OAuth Client ID and Client Secret from Google Cloud Console to enable Sign-in with Google.'}
              </p>

              {/* Enable toggle */}
              <div className="flex items-center justify-between py-3 border-y border-border">
                <div>
                  <div className="font-medium">{t('admin_google_oauth_enabled')}</div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {lang === 'fa' ? 'وقتی روشن باشه، دکمهٔ گوگل در صفحات ورود و ثبت‌نام نمایش داده می‌شه.' : 'When ON, the Google button is shown on login & register pages.'}
                  </p>
                </div>
                <Switch
                  checked={googleOAuth.enabled}
                  onCheckedChange={async (v) => {
                    try {
                      await adminAPI.updateGoogleOAuth({ enabled: v });
                      setGoogleOAuth(p => ({ ...p, enabled: v }));
                      toast.success(v ? t('admin_google_oauth_enabled_msg') : t('admin_google_oauth_disabled_msg'));
                    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
                  }}
                  data-testid="admin-google-oauth-toggle"
                />
              </div>

              <div className="space-y-2">
                <Label>{t('admin_google_client_id')}</Label>
                <Input
                  type="text"
                  value={googleOAuth.client_id}
                  onChange={(e) => setGoogleOAuth(p => ({ ...p, client_id: e.target.value }))}
                  placeholder="123456789-abc.apps.googleusercontent.com"
                  className="font-mono text-xs"
                  data-testid="admin-google-client-id-input"
                  dir="ltr"
                />
              </div>

              <div className="space-y-2">
                <Label>
                  {t('admin_google_client_secret')}
                  {googleOAuth.has_secret && (
                    <span className="ms-2 text-[10px] font-mono text-muted-foreground">
                      ({lang === 'fa' ? 'موجود' : 'set'}: {googleOAuth.client_secret_masked})
                    </span>
                  )}
                </Label>
                <Input
                  type="password"
                  value={googleOAuth.client_secret}
                  onChange={(e) => setGoogleOAuth(p => ({ ...p, client_secret: e.target.value }))}
                  placeholder={googleOAuth.has_secret ? (lang === 'fa' ? 'برای تغییر، مقدار جدید را وارد کنید' : 'Enter new value to change') : 'GOCSPX-...'}
                  className="font-mono text-xs"
                  data-testid="admin-google-client-secret-input"
                  dir="ltr"
                />
              </div>

              <Button
                onClick={async () => {
                  setGoogleOAuthSaving(true);
                  try {
                    const payload = { client_id: googleOAuth.client_id };
                    if (googleOAuth.client_secret && googleOAuth.client_secret.trim()) {
                      payload.client_secret = googleOAuth.client_secret;
                    }
                    await adminAPI.updateGoogleOAuth(payload);
                    toast.success(t('admin_google_oauth_saved'));
                    setGoogleOAuth(p => ({ ...p, client_secret: '' }));
                    fetchGoogleOAuth();
                  } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
                  setGoogleOAuthSaving(false);
                }}
                disabled={googleOAuthSaving}
                data-testid="admin-google-oauth-save-btn"
              >
                {googleOAuthSaving ? <Loader2 className="w-4 h-4 animate-spin me-2" /> : <Save className="w-4 h-4 me-2" />}
                {t('admin_save_settings')}
              </Button>
            </div>

            {/* ── Record Types ── */}
            <div className="rounded-sm border border-border bg-card p-6 space-y-5" data-testid="admin-record-types-section">
              <div className="flex items-center gap-3 mb-2">
                <Database className="w-5 h-5 text-primary" />
                <h3 className="text-lg font-semibold">{lang === 'fa' ? 'نوع‌های رکورد DNS' : 'DNS Record Types'}</h3>
                <Button variant="ghost" size="sm" onClick={fetchRecordTypes} data-testid="admin-record-types-refresh">
                  <RefreshCw className="w-4 h-4" />
                </Button>
              </div>
              <p className="text-xs text-muted-foreground -mt-2">
                {lang === 'fa'
                  ? 'نوع‌های رکوردی که می‌خواهید کاربران بتوانند بسازند را روشن/خاموش کنید. نوع خاموش در فرم ساخت رکورد به کاربر نمایش داده نمی‌شود. اگر همه خاموش باشند، ساخت رکورد کاملاً غیرفعال می‌شود.'
                  : 'Toggle which record types users can create. A disabled type is hidden in the create form. If all are disabled, record creation is turned off entirely.'}
              </p>
              {recordTypes.length > 0 && recordTypes.filter(rt => rt.enabled).length === 0 && (
                <div className="border border-destructive/40 bg-destructive/5 text-destructive font-mono text-[11px] p-3 rounded-sm" data-testid="admin-record-types-all-off">
                  {lang === 'fa' ? '⚠ همه نوع‌ها خاموش‌اند — ساخت رکورد برای کاربران غیرفعال است.' : '⚠ All types are off — record creation is disabled for users.'}
                </div>
              )}
              <div className="divide-y divide-border border border-border rounded-sm">
                {recordTypes.map(rt => (
                  <div key={rt.type} className="flex items-center justify-between px-4 py-3" data-testid={`admin-record-type-row-${rt.type}`}>
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-sm font-semibold w-14">{rt.type}</span>
                      <span className="font-mono text-[11px] text-muted-foreground">
                        {rt.enabled ? (lang === 'fa' ? 'فعال' : 'enabled') : (lang === 'fa' ? 'خاموش' : 'disabled')}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {recordTypesSaving === rt.type && <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />}
                      <Switch
                        checked={rt.enabled}
                        disabled={recordTypesSaving === rt.type}
                        onCheckedChange={(v) => handleToggleRecordType(rt.type, v)}
                        data-testid={`admin-record-type-toggle-${rt.type}`}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>

      {/* === DIALOGS === */}

      {/* Delete User */}
      <AlertDialog open={!!deleteUserId} onOpenChange={() => setDeleteUserId(null)}>
        <AlertDialogContent data-testid="admin-delete-user-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>{t('admin_delete_user')}</AlertDialogTitle>
            <AlertDialogDescription>{t('admin_delete_user_confirm')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel><X className="w-4 h-4 me-1" />{t('cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteUser} className="bg-destructive text-destructive-foreground hover:bg-destructive/90" data-testid="admin-delete-user-confirm-btn"><Trash2 className="w-4 h-4 me-1" />{t('delete_confirm')}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Change Plan */}
      <Dialog open={!!planDialogUser} onOpenChange={() => setPlanDialogUser(null)}>
        <DialogContent className="sm:max-w-sm" data-testid="admin-change-plan-dialog">
          <DialogHeader><DialogTitle>{t('admin_change_plan')}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {planDialogUser?.email} &mdash; {lang === 'fa' ? 'فعلی:' : 'Current:'} <strong>{planDialogUser?.plan}</strong>
            </p>
            <Select value={selectedPlan} onValueChange={setSelectedPlan}>
              <SelectTrigger data-testid="admin-plan-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                {plans.map(p => (
                  <SelectItem key={p.plan_id} value={p.plan_id}>{p.name} ({p.record_limit === 0 ? '∞' : p.record_limit} records)</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPlanDialogUser(null)}><X className="w-4 h-4 me-1" />{t('cancel')}</Button>
            <Button onClick={handleChangePlan} disabled={planLoading} data-testid="admin-plan-save-btn">
              {planLoading ? <Loader2 className="w-4 h-4 animate-spin me-2" /> : <Save className="w-4 h-4 me-1" />}{t('save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Change Password */}
      <Dialog open={!!passwordDialogUser} onOpenChange={() => setPasswordDialogUser(null)}>
        <DialogContent className="sm:max-w-sm" data-testid="admin-change-password-dialog">
          <DialogHeader><DialogTitle><KeyRound className="w-5 h-5 inline me-2" />{t('admin_change_password')}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">{passwordDialogUser?.email}</p>
            <div className="space-y-2">
              <Label>{t('admin_new_password')}</Label>
              <Input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="••••••••"
                minLength={6}
                data-testid="admin-new-password-input"
              />
              {newPassword.length > 0 && newPassword.length < 6 && (
                <p className="text-xs text-destructive">{lang === 'fa' ? 'حداقل ۶ کاراکتر' : 'Minimum 6 characters'}</p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPasswordDialogUser(null)}><X className="w-4 h-4 me-1" />{t('cancel')}</Button>
            <Button onClick={handleChangePassword} disabled={passwordLoading || newPassword.length < 6} data-testid="admin-password-save-btn">
              {passwordLoading ? <Loader2 className="w-4 h-4 animate-spin me-2" /> : <Save className="w-4 h-4 me-1" />}{t('save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View User Records */}
      <Dialog open={!!userRecordsDialog} onOpenChange={() => setUserRecordsDialog(null)}>
        <DialogContent className="sm:max-w-2xl" data-testid="admin-user-records-dialog">
          <DialogHeader><DialogTitle>{t('admin_user_records')} &mdash; {userRecordsDialog?.email}</DialogTitle></DialogHeader>
          {userRecords.length === 0 ? (
            <p className="text-center text-muted-foreground py-6">{t('admin_no_records')}</p>
          ) : (
            <div className="overflow-x-auto max-h-80">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('table_type')}</TableHead>
                    <TableHead>{t('table_name')}</TableHead>
                    <TableHead>{t('table_content')}</TableHead>
                    <TableHead className="text-end">{t('table_actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {userRecords.map((rec) => (
                    <TableRow key={rec.id}>
                      <TableCell><Badge variant="outline" className={typeColors[rec.record_type] || ''}>{rec.record_type}</Badge></TableCell>
                      <TableCell className="font-mono text-sm">{rec.full_name}</TableCell>
                      <TableCell className="font-mono text-sm">{rec.content}</TableCell>
                      <TableCell className="text-end">
                        <Button variant="ghost" size="sm" className="text-destructive" onClick={() => setDeleteRecordId(rec.id)}>
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Delete Record */}
      <AlertDialog open={!!deleteRecordId} onOpenChange={() => setDeleteRecordId(null)}>
        <AlertDialogContent data-testid="admin-delete-record-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>{t('form_delete')}</AlertDialogTitle>
            <AlertDialogDescription>{t('form_delete_confirm')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel><X className="w-4 h-4 me-1" />{t('cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteRecord} className="bg-destructive text-destructive-foreground hover:bg-destructive/90" data-testid="admin-delete-record-confirm-btn"><Trash2 className="w-4 h-4 me-1" />{t('delete_confirm')}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Create Record for User */}
      <Dialog open={showCreateRecordDialog} onOpenChange={setShowCreateRecordDialog}>
        <DialogContent className="sm:max-w-md" data-testid="admin-create-record-dialog">
          <DialogHeader><DialogTitle>{t('admin_add_record')}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            {createRecordError && <div className="p-3 rounded-lg bg-destructive/10 text-destructive text-sm border border-destructive/20">{createRecordError}</div>}
            <div className="space-y-2">
              <Label>{t('admin_select_user')}</Label>
              <Select value={createRecordForm.user_id} onValueChange={(v) => setCreateRecordForm(p => ({ ...p, user_id: v }))}>
                <SelectTrigger data-testid="admin-create-user-select"><SelectValue placeholder={t('admin_select_user')} /></SelectTrigger>
                <SelectContent>{nonAdminUsers.map(u => <SelectItem key={u.id} value={u.id}>{u.name} ({u.email})</SelectItem>)}</SelectContent>
              </Select>
            </div>
            {zones.length > 1 && (
              <div className="space-y-2">
                <Label>{lang === 'fa' ? 'دامنه' : 'Domain'}</Label>
                <Select value={createRecordForm.zone_id} onValueChange={(v) => setCreateRecordForm(p => ({ ...p, zone_id: v }))}>
                  <SelectTrigger data-testid="admin-create-zone-select"><SelectValue placeholder={lang === 'fa' ? 'انتخاب دامنه' : 'Select domain'} /></SelectTrigger>
                  <SelectContent>
                    {zones.map(z => (
                      <SelectItem key={z.id} value={z.id}>{z.domain}{z.is_primary ? (lang === 'fa' ? ' (اصلی)' : ' (primary)') : ''}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="space-y-2">
              <Label>{t('form_subdomain')}</Label>
              <div className="flex items-center gap-2">
                <Input value={createRecordForm.name} onChange={(e) => setCreateRecordForm(p => ({ ...p, name: e.target.value }))} placeholder="mysite" data-testid="admin-create-subdomain-input" />
                <span className="text-sm text-muted-foreground whitespace-nowrap">.{(zones.find(z => z.id === createRecordForm.zone_id) || {}).domain || DNS_DOMAIN}</span>
              </div>
            </div>
            <div className="space-y-2">
              <Label>{t('form_type')}</Label>
              <Select value={createRecordForm.record_type} onValueChange={(v) => setCreateRecordForm(p => ({ ...p, record_type: v }))}>
                <SelectTrigger data-testid="admin-create-type-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="A">A</SelectItem>
                  <SelectItem value="AAAA">AAAA</SelectItem>
                  <SelectItem value="CNAME">CNAME</SelectItem>
                  <SelectItem value="NS">NS</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>{t('form_content')}</Label>
              <Input value={createRecordForm.content} onChange={(e) => setCreateRecordForm(p => ({ ...p, content: e.target.value }))} placeholder="192.168.1.1" data-testid="admin-create-content-input" />
            </div>
            <div className="flex items-center justify-between">
              <Label>{t('form_proxied')}</Label>
              <Switch checked={createRecordForm.proxied} onCheckedChange={(v) => setCreateRecordForm(p => ({ ...p, proxied: v }))} data-testid="admin-create-proxied-switch" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateRecordDialog(false)}><X className="w-4 h-4 me-1" />{t('cancel')}</Button>
            <Button onClick={handleCreateRecord} disabled={createRecordLoading || !createRecordForm.user_id || !createRecordForm.name || !createRecordForm.content} data-testid="admin-create-record-btn">
              {createRecordLoading && <Loader2 className="w-4 h-4 animate-spin me-2" />}<Plus className="w-4 h-4 me-1" />{t('form_create')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create/Edit Plan */}
      <Dialog open={showPlanDialog} onOpenChange={setShowPlanDialog}>
        <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto" data-testid="admin-plan-dialog">
          <DialogHeader>
            <DialogTitle>{editingPlan ? t('admin_edit_plan') : t('admin_add_plan')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {planFormError && <div className="p-3 rounded-lg bg-destructive/10 text-destructive text-sm border border-destructive/20">{planFormError}</div>}
            {!editingPlan && (
              <div className="space-y-2">
                <Label>{t('admin_plan_id')}</Label>
                <Input value={planForm.plan_id} onChange={(e) => setPlanForm(p => ({ ...p, plan_id: e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, '') }))} placeholder="e.g. starter" data-testid="admin-plan-id-input" />
              </div>
            )}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{t('admin_plan_name')}</Label>
                <Input value={planForm.name} onChange={(e) => setPlanForm(p => ({ ...p, name: e.target.value }))} placeholder="Pro" data-testid="admin-plan-name-input" />
              </div>
              <div className="space-y-2">
                <Label>{t('admin_plan_name_fa')}</Label>
                <Input value={planForm.name_fa} onChange={(e) => setPlanForm(p => ({ ...p, name_fa: e.target.value }))} dir="rtl" placeholder="حرفه‌ای" data-testid="admin-plan-namefa-input" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{t('admin_plan_price')}</Label>
                <Input value={planForm.price} onChange={(e) => setPlanForm(p => ({ ...p, price: e.target.value }))} placeholder="۵۰,۰۰۰ تومان/ماه" data-testid="admin-plan-price-input" />
              </div>
              <div className="space-y-2">
                <Label>{t('admin_plan_price_fa')}</Label>
                <Input value={planForm.price_fa} onChange={(e) => setPlanForm(p => ({ ...p, price_fa: e.target.value }))} dir="rtl" placeholder="۵۰,۰۰۰ تومان/ماه" data-testid="admin-plan-pricefa-input" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{t('admin_plan_limit')}</Label>
                <Input type="number" min="0" value={planForm.record_limit} onChange={(e) => setPlanForm(p => ({ ...p, record_limit: parseInt(e.target.value) || 0 }))} data-testid="admin-plan-limit-input" />
              </div>
              <div className="space-y-2">
                <Label>{t('admin_plan_sort')}</Label>
                <Input type="number" value={planForm.sort_order} onChange={(e) => setPlanForm(p => ({ ...p, sort_order: parseInt(e.target.value) || 0 }))} data-testid="admin-plan-sort-input" />
              </div>
            </div>
            <div className="space-y-2">
              <Label>{t('admin_plan_features')}</Label>
              <Textarea rows={3} value={planForm.features} onChange={(e) => setPlanForm(p => ({ ...p, features: e.target.value }))} placeholder="One feature per line" data-testid="admin-plan-features-input" />
            </div>
            <div className="space-y-2">
              <Label>{t('admin_plan_features_fa')}</Label>
              <Textarea rows={3} value={planForm.features_fa} onChange={(e) => setPlanForm(p => ({ ...p, features_fa: e.target.value }))} dir="rtl" placeholder="هر خط یک امکان" data-testid="admin-plan-featuresfa-input" />
            </div>
            <div className="flex items-center justify-between">
              <Label>{t('admin_plan_popular')}</Label>
              <Switch checked={planForm.popular} onCheckedChange={(v) => setPlanForm(p => ({ ...p, popular: v }))} data-testid="admin-plan-popular-switch" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowPlanDialog(false)}><X className="w-4 h-4 me-1" />{t('cancel')}</Button>
            <Button onClick={handleSavePlan} disabled={planFormLoading || (!editingPlan && !planForm.plan_id) || !planForm.name} data-testid="admin-plan-save-btn">
              {planFormLoading && <Loader2 className="w-4 h-4 animate-spin me-2" />}
              <Save className="w-4 h-4 me-1" />{t('save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Plan */}
      <AlertDialog open={!!deletePlanId} onOpenChange={() => setDeletePlanId(null)}>
        <AlertDialogContent data-testid="admin-delete-plan-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>{t('admin_delete_plan')}</AlertDialogTitle>
            <AlertDialogDescription>{t('admin_delete_plan_confirm')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel><X className="w-4 h-4 me-1" />{t('cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeletePlan} className="bg-destructive text-destructive-foreground hover:bg-destructive/90" data-testid="admin-delete-plan-confirm-btn"><Trash2 className="w-4 h-4 me-1" />{t('delete_confirm')}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Bulk Change Plan */}
      <Dialog open={showBulkPlanDialog} onOpenChange={setShowBulkPlanDialog}>
        <DialogContent className="sm:max-w-sm" data-testid="bulk-plan-dialog">
          <DialogHeader>
            <DialogTitle>{t('admin_bulk_change_plan')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {t('admin_bulk_confirm_plan').replace('{count}', selectedUserIds.size)}
            </p>
            <Select value={bulkPlan} onValueChange={setBulkPlan}>
              <SelectTrigger data-testid="bulk-plan-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                {plans.map(p => (
                  <SelectItem key={p.plan_id} value={p.plan_id}>{p.name} ({p.record_limit === 0 ? '∞' : p.record_limit} records)</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowBulkPlanDialog(false)}><X className="w-4 h-4 me-1" />{t('cancel')}</Button>
            <Button onClick={handleBulkPlanChange} disabled={bulkLoading} data-testid="bulk-plan-confirm-btn">
              {bulkLoading ? <Loader2 className="w-4 h-4 animate-spin me-2" /> : <Save className="w-4 h-4 me-1" />}{t('save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Delete */}
      <AlertDialog open={showBulkDeleteDialog} onOpenChange={setShowBulkDeleteDialog}>
        <AlertDialogContent data-testid="bulk-delete-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>{t('admin_bulk_delete')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('admin_bulk_confirm_delete').replace('{count}', selectedUserIds.size)}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel><X className="w-4 h-4 me-1" />{t('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleBulkDelete}
              disabled={bulkLoading}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              data-testid="bulk-delete-confirm-btn"
            >
              {bulkLoading ? <Loader2 className="w-4 h-4 animate-spin me-2" /> : <Trash2 className="w-4 h-4 me-1" />}{t('delete_confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* ═══ ADMIN IMPORT CSV DIALOG ═══ */}
      <Dialog open={showAdminImportDialog} onOpenChange={setShowAdminImportDialog}>
        <DialogContent className="sm:max-w-2xl rounded-sm border-border" data-testid="admin-import-csv-dialog">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold tracking-tight">{t('admin_import_csv_title')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="flex items-center gap-2 flex-wrap">
              <Button size="sm" variant="outline" onClick={async () => {
                try {
                  const res = await adminAPI.downloadAdminTemplate();
                  downloadBlob(res.data, 'all-records-template.csv');
                } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
              }} data-testid="admin-download-template-btn">
                <Download className="w-3.5 h-3.5 me-1.5" />{t('download_template')}
              </Button>
              <label className="inline-flex items-center gap-1.5 h-9 px-3 border border-border bg-card hover:border-primary hover:text-primary text-xs cursor-pointer rounded-sm transition-colors">
                <Upload className="w-3.5 h-3.5" />{t('choose_csv_file')}
                <input type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => {
                  const file = e.target.files?.[0]; if (!file) return;
                  const reader = new FileReader();
                  reader.onload = (ev) => setAdminImportCsvText(String(ev.target?.result || ''));
                  reader.readAsText(file);
                }} data-testid="admin-import-file-input" />
              </label>
              <span className="text-[11px] font-mono text-muted-foreground ms-auto">
                {t('admin_import_hint_cols')}
              </span>
            </div>
            <textarea
              value={adminImportCsvText}
              onChange={(e) => setAdminImportCsvText(e.target.value)}
              rows={10}
              placeholder={`user_email,name,record_type,content,ttl,proxied,zone_domain\nuser1@example.com,www,A,1.2.3.4,1,false,${zones[0]?.domain || 'example.com'}`}
              className="w-full border border-border bg-background rounded-sm p-3 font-mono text-xs focus:border-primary focus:outline-none resize-none"
              data-testid="admin-import-csv-textarea"
            />
            {adminImportResult && (
              <div className="border border-border rounded-sm p-3 space-y-2 max-h-52 overflow-y-auto" data-testid="admin-import-result">
                <div className="font-mono text-xs flex gap-4 flex-wrap">
                  <span className="text-green-600">✓ {t('import_success_count')}: {adminImportResult.success?.length || 0}</span>
                  <span className="text-destructive">✗ {t('import_failed_count')}: {adminImportResult.failed?.length || 0}</span>
                  <span className="text-muted-foreground">{t('import_total')}: {adminImportResult.total || 0}</span>
                </div>
                {adminImportResult.failed?.length > 0 && (
                  <div className="space-y-1">
                    {adminImportResult.failed.map((f, i) => (
                      <div key={i} className="text-[11px] font-mono text-destructive/90">
                        line {f.line}: {f.user_email || '-'} / {f.name || '-'} — {f.error}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAdminImportDialog(false)} data-testid="admin-import-cancel-btn">
              <X className="w-4 h-4 me-1" />{t('btn_close')}
            </Button>
            <Button onClick={async () => {
              if (!adminImportCsvText.trim()) return;
              setAdminImportLoading(true); setAdminImportResult(null);
              try {
                const res = await adminAPI.importAllRecordsCSV(adminImportCsvText);
                setAdminImportResult(res.data);
                fetchAllRecords(); fetchUsers();
              } catch (err) {
                setAdminImportResult({ success: [], failed: [{ line: 0, name: '-', error: err.response?.data?.detail || 'Import failed' }], total: 0 });
              } finally { setAdminImportLoading(false); }
            }} disabled={adminImportLoading || !adminImportCsvText.trim()} data-testid="admin-import-submit-btn">
              {adminImportLoading ? <Loader2 className="w-4 h-4 animate-spin me-1" /> : <Upload className="w-4 h-4 me-1" />}
              {t('import_csv')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
