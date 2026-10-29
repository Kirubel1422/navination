import { render } from "@testing-library/react";
import type { ReactElement } from "react";

import { TooltipProvider } from "@/components/ui/tooltip";
import { LocaleProvider, writeLocale } from "@/lib/i18n/locale";
import type { Locale } from "@/lib/api/types";

export function renderWithLocale(ui: ReactElement, locale: Locale = "en") {
  writeLocale(locale);
  return render(
    <LocaleProvider>
      <TooltipProvider>{ui}</TooltipProvider>
    </LocaleProvider>,
  );
}
