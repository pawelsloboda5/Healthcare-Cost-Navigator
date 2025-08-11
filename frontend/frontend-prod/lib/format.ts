export function formatCurrency(amount?: number | string) {
  if (amount === null || amount === undefined || amount === "") return "N/A";
  const num = Number(amount);
  if (Number.isNaN(num)) return String(amount);
  return "$" + num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function formatRating(rating?: number | string) {
  if (rating === null || rating === undefined || rating === "") return "N/A";
  const num = Number(rating);
  if (Number.isNaN(num)) return String(rating);
  return `${num.toFixed(1)}/10`;
}

export function friendlyError(error: unknown, context: string) {
  const maybeObj = error as { message?: string } | null | undefined;
  const message = maybeObj && typeof maybeObj === "object" && "message" in maybeObj && maybeObj.message
    ? maybeObj.message
    : String(error);
  return `Error in ${context}: ${message}`;
}

