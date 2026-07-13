export function dday(deadline: string) {
  const now = new Date();
  const target = new Date(`${deadline}T23:59:59`);
  const days = Math.ceil((target.getTime() - now.getTime()) / 86400000);
  return days >= 0 ? `D-${days}` : "마감";
}

export function money(value: number) {
  return new Intl.NumberFormat("ko-KR").format(value);
}
