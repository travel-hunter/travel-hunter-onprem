export type ShareMethod = "share" | "clipboard" | "legacy";

export type ShareLinkPayload = {
  title: string;
  text: string;
  url: string;
};

export type ShareLinkEnvironment = {
  navigator?: Pick<Navigator, "share" | "clipboard">;
  document?: Pick<Document, "body" | "createElement"> & {
    execCommand?: (command: string) => boolean;
  };
};

type ShareNavigator = Navigator & {
  share?: (data: ShareData) => Promise<void>;
  clipboard?: {
    writeText?: (text: string) => Promise<void>;
  };
};

type ShareDocument = Document & {
  execCommand?: (command: string) => boolean;
};

function legacyCopyText(text: string, shareDocument: ShareDocument = document as ShareDocument) {
  const execCommand = shareDocument.execCommand;
  if (typeof execCommand !== "function") {
    throw new Error("Legacy copy unavailable");
  }

  const textarea = shareDocument.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.top = "-9999px";
  textarea.style.opacity = "0";
  shareDocument.body.appendChild(textarea);
  textarea.select();
  const copied = execCommand.call(shareDocument, "copy");
  shareDocument.body.removeChild(textarea);
  if (!copied) {
    throw new Error("Legacy copy failed");
  }
}

export async function shareLinkWithFallback(
  { title, text, url }: ShareLinkPayload,
  env: ShareLinkEnvironment = {},
): Promise<ShareMethod> {
  const shareNavigator = (env.navigator ?? navigator) as ShareNavigator;

  if (typeof shareNavigator.share === "function") {
    try {
      await shareNavigator.share({ title, text, url });
      return "share";
    } catch {
      // Fall through to clipboard and legacy copy.
    }
  }

  if (typeof shareNavigator.clipboard?.writeText === "function") {
    try {
      await shareNavigator.clipboard.writeText(url);
      return "clipboard";
    } catch {
      // Fall through to the legacy copy path.
    }
  }

  const shareDocument = (env.document ?? document) as ShareDocument;
  legacyCopyText(url, shareDocument);
  return "legacy";
}
