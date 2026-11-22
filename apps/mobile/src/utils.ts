export const uid = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;

export const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** 한글 받침 여부에 따라 조사 선택: josa('곰팡이', '이', '가') → '곰팡이가' */
export function josa(word: string, withBatchim: string, withoutBatchim: string) {
  const code = word.charCodeAt(word.length - 1) - 0xac00;
  const hasBatchim = code >= 0 && code <= 11171 && code % 28 !== 0;
  return word + (hasBatchim ? withBatchim : withoutBatchim);
}

export function today() {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}.${p(d.getMonth() + 1)}.${p(d.getDate())}`;
}

export function isValidDate(s: string) {
  const m = /^(\d{4})\.(\d{2})\.(\d{2})$/.exec(s);
  if (!m) return false;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return d.getMonth() === Number(m[2]) - 1 && d.getTime() <= Date.now();
}
