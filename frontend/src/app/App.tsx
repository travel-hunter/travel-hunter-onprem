import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { PublicLayout, ServiceLayout } from "../components/AppLayout";
import { AiResultsPage, FriendInvitePage, ItineraryCreatePage, ItineraryDetailPage, ItineraryListPage } from "../pages/ItineraryPages";
import { ForgotPasswordPage, LoginPage, NicknameSetupPage, OAuthCallbackPage, OAuthStartPage, ResetPasswordPage, SignupPage, SignupVerifyPage, SocialSignupAgreementPage } from "../pages/AuthPages";
import { AppliedPolicyLinksPage } from "../pages/AppliedPolicyLinksPage";
import { HomePage } from "../pages/HomePage";
import { InviteAcceptPage } from "../pages/InviteAcceptPage";
import { MyPage } from "../pages/MyPage";
import { PolicyDetailPage, PolicyListPage } from "../pages/PolicyPages";
import { ProfileSetupPage } from "../pages/ProfileSetupPage";
import { LoadingState } from "../components/ui";
import { AdminAuditLogsPage, AdminDashboardPage, AdminForbiddenPage, AdminLayout, AdminPoliciesPage, AdminPolicyEditorPage, AdminUserDetailPage, AdminUsersPage } from "../pages/admin/AdminPages";
import { getOnboardingPath, isOnboardingRoute, withRedirect } from "./onboarding";
import { useSession } from "./session";

export function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route path="/" element={<LoginPage />} />
        <Route path="/onboarding" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/signup/verify" element={<SignupVerifyPage />} />
        <Route path="/signup/social-agreement" element={<SocialSignupAgreementPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/oauth/:provider/start" element={<OAuthStartPage />} />
        <Route path="/oauth/callback" element={<OAuthCallbackPage />} />
        <Route path="/invites/:inviteToken/accept" element={<InviteAcceptPage />} />
      </Route>
      <Route element={<ProtectedRoute />}>
        <Route element={<AdminRoute />}>
          <Route element={<AdminLayout />}>
            <Route path="/admin" element={<AdminDashboardPage />} />
            <Route path="/admin/users" element={<AdminUsersPage />} />
            <Route path="/admin/users/:userId" element={<AdminUserDetailPage />} />
            <Route path="/admin/policies" element={<AdminPoliciesPage />} />
            <Route path="/admin/policies/new" element={<AdminPolicyEditorPage mode="create" />} />
            <Route path="/admin/policies/:policyId" element={<AdminPolicyEditorPage />} />
            <Route path="/admin/audit-logs" element={<AdminAuditLogsPage />} />
          </Route>
        </Route>
        <Route element={<PublicLayout />}>
          <Route path="/nickname-setup" element={<NicknameSetupPage />} />
          <Route path="/profile-setup" element={<ProfileSetupPage />} />
        </Route>
        <Route element={<ServiceLayout />}>
          <Route path="/home" element={<HomePage />} />
          <Route path="/policies" element={<PolicyListPage />} />
          <Route path="/policies/:policyId" element={<PolicyDetailPage />} />
          <Route path="/trips" element={<ItineraryListPage />} />
          <Route path="/trips/new" element={<ItineraryCreatePage />} />
          <Route path="/trips/:tripId" element={<ItineraryDetailPage />} />
          <Route path="/ai-results" element={<AiResultsPage />} />
          <Route path="/friend-invite" element={<FriendInvitePage />} />
          <Route path="/applied-policies" element={<AppliedPolicyLinksPage />} />
          <Route path="/mypage" element={<MyPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function AdminRoute() {
  const { currentUser, isSessionBootstrapping } = useSession();
  if (isSessionBootstrapping && !currentUser) {
    return <LoadingState label="관리자 권한을 확인하는 중입니다" />;
  }
  if (currentUser?.role !== "admin") {
    return <AdminForbiddenPage />;
  }
  return <Outlet />;
}

function ProtectedRoute() {
  const { currentUser, isSessionBootstrapping } = useSession();
  const location = useLocation();
  if (isSessionBootstrapping && !currentUser) {
    return <LoadingState label="세션을 확인하는 중입니다" />;
  }
  if (!currentUser) {
    const redirectTo = `${location.pathname}${location.search}${location.hash}`;
    return <Navigate to={`/login?redirect=${encodeURIComponent(redirectTo)}`} replace />;
  }
  const onboardingPath = getOnboardingPath(currentUser);
  const mustConfirmNicknameFirst = location.pathname === "/profile-setup" && onboardingPath === "/nickname-setup";
  if (onboardingPath && (!isOnboardingRoute(location.pathname) || mustConfirmNicknameFirst)) {
    const redirectTo = `${location.pathname}${location.search}${location.hash}`;
    return <Navigate to={withRedirect(onboardingPath, redirectTo)} replace />;
  }
  return <Outlet />;
}
