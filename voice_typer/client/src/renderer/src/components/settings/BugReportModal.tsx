// components/settings/BugReportModal.tsx
//
// In-app bug reporter. Replaces the old "Report a Bug" button, which sent
// the user to the project's public issue tracker — a shipped application
// should collect a report without leaving the app and without exposing a
// repository.
//
// The user types what happened, attaches screenshots, and presses Send.
// The host command writes the images next to the generated report and
// hands a `mailto:` draft to the OS mail client, so the report reaches the
// maintainer through a channel the user already has.

import {
	Cancel01Icon,
	Image01Icon,
	SentIcon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { memo, useEffect, useRef, useState } from "react";
import { Modal, ModalFooter } from "@/components/common/Modal";
import { Button } from "@/components/ui/button";
import {
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useSnackbar } from "@/hooks/useSnackbar";
import { useT } from "@/i18n/i18n";
import { collectReportContext, SUPPORT_EMAIL } from "@/lib/support";
import pkg from "../../../../../package.json";

const APP_VERSION = pkg.version as string;

/** Mirrors `MAX_ATTACHMENTS` in the host's `send_bug_report` command. */
const MAX_ATTACHMENTS = 5;

interface Attachment {
	/** Stable identity for React keys: two screenshots can share a filename,
	 *  and the list is mutated by removal. */
	id: string;
	name: string;
	dataUrl: string;
}

/** Monotonic source of {@link Attachment} ids (module-scope so ids stay
 *  unique across mounts). */
let attachmentSeq = 0;

function readFileAsDataUrl(file: File): Promise<string> {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () => resolve(String(reader.result));
		reader.onerror = () => reject(reader.error ?? new Error("read failed"));
		reader.readAsDataURL(file);
	});
}

interface BugReportModalProps {
	open: boolean;
	onClose: () => void;
}

function BugReportModalInner({ open, onClose }: BugReportModalProps) {
	const t = useT();
	const { showSnack } = useSnackbar();

	const [title, setTitle] = useState("");
	const [description, setDescription] = useState("");
	const [attachments, setAttachments] = useState<Attachment[]>([]);
	const [sending, setSending] = useState(false);
	const fileInputRef = useRef<HTMLInputElement | null>(null);

	// A dismissed report must not reappear on the next open: the modal is
	// mounted for the page's lifetime, so the draft is cleared here rather
	// than relying on unmount.
	useEffect(() => {
		if (open) return;
		setTitle("");
		setDescription("");
		setAttachments([]);
		setSending(false);
	}, [open]);

	const addFiles = async (files: FileList | null) => {
		if (!files || files.length === 0) return;
		const room = MAX_ATTACHMENTS - attachments.length;
		if (room <= 0) {
			showSnack(
				t("settings.bugReport.tooManyImages", {
					count: String(MAX_ATTACHMENTS),
				}),
				"error",
			);
			return;
		}
		const accepted: Attachment[] = [];
		for (const file of Array.from(files).slice(0, room)) {
			if (!file.type.startsWith("image/")) {
				showSnack(t("settings.bugReport.attachmentFailed"), "error");
				continue;
			}
			try {
				accepted.push({
					id: `bug-attachment-${++attachmentSeq}`,
					name: file.name,
					dataUrl: await readFileAsDataUrl(file),
				});
			} catch {
				showSnack(t("settings.bugReport.attachmentFailed"), "error");
			}
		}
		if (accepted.length > 0) {
			setAttachments((current) => [...current, ...accepted]);
		}
	};

	const removeAttachment = (index: number) => {
		setAttachments((current) => current.filter((_, i) => i !== index));
	};

	const handleSend = async () => {
		const trimmed = description.trim();
		if (!trimmed) return;

		const subject = `[Bug] ${
			title.trim() || (trimmed.split("\n")[0] ?? "").slice(0, 80)
		}`;
		const body = [
			trimmed,
			"",
			"---",
			...collectReportContext(APP_VERSION),
		].join("\n");

		setSending(true);
		try {
			const send = window.window_?.sendBugReport;
			if (typeof send !== "function") {
				// Sandboxed runtimes (the bubble window) omit the namespace.
				// The report is still worth keeping, so hand the user the
				// text instead of silently dropping it.
				await navigator.clipboard
					?.writeText(`${subject}\n\n${body}`)
					.catch(() => undefined);
				showSnack(t("settings.bugReport.copied"), "info");
				onClose();
				return;
			}
			const result = await send({
				to: SUPPORT_EMAIL,
				subject,
				body,
				attachments,
			});
			if (result?.success) {
				const attached = result.attachments ?? 0;
				showSnack(
					attached > 0
						? t("settings.bugReport.sentWithAttachments", {
								count: String(attached),
							})
						: t("settings.bugReport.sent"),
					"success",
				);
				onClose();
			} else {
				showSnack(result?.error || t("settings.bugReport.sendFailed"), "error");
			}
		} catch (err) {
			console.error("[renderer:BugReportModal] send_bug_report failed:", err);
			showSnack(t("settings.bugReport.sendFailed"), "error");
		} finally {
			setSending(false);
		}
	};

	const canSend = description.trim().length > 0 && !sending;

	return (
		<Modal
			open={open}
			onClose={onClose}
			size="lg"
			className="max-h-[85vh] grid-rows-[minmax(0,1fr)] overflow-hidden shadow-none"
		>
			<div className="-mx-6 -mb-6 flex min-h-0 flex-col gap-5 overflow-y-auto px-6 pb-6">
				<DialogHeader>
					<DialogTitle>{t("settings.bugReport.title")}</DialogTitle>
					<DialogDescription>
						{t("settings.bugReport.description")}
					</DialogDescription>
				</DialogHeader>

				<div className="flex flex-col gap-2">
					<label
						htmlFor="bug-report-title"
						className="text-sm font-medium text-foreground"
					>
						{t("settings.bugReport.titleLabel")}
					</label>
					<Input
						id="bug-report-title"
						value={title}
						onChange={(e) => setTitle(e.target.value)}
						placeholder={t("settings.bugReport.titlePlaceholder")}
						className="w-full"
					/>
				</div>

				<div className="flex flex-col gap-2">
					<label
						htmlFor="bug-report-description"
						className="text-sm font-medium text-foreground"
					>
						{t("settings.bugReport.descriptionLabel")}
					</label>
					<Textarea
						id="bug-report-description"
						value={description}
						onChange={(e) => setDescription(e.target.value)}
						placeholder={t("settings.bugReport.descriptionPlaceholder")}
						rows={6}
						required
					/>
				</div>

				<div className="flex flex-col gap-2">
					<span className="text-sm font-medium text-foreground">
						{t("settings.bugReport.attachmentsLabel")}
					</span>
					{/* biome-ignore lint/a11y/noStaticElementInteractions: the drop zone is a pointer-only enhancement; the adjacent "Add images" button is the keyboard path */}
					<div
						onDragOver={(e) => e.preventDefault()}
						onDrop={(e) => {
							e.preventDefault();
							void addFiles(e.dataTransfer?.files ?? null);
						}}
						className="flex flex-col gap-3 rounded-lg border border-border/8 border-dashed p-3"
					>
						{attachments.length > 0 && (
							<ul className="flex flex-wrap gap-2">
								{attachments.map((attachment, index) => (
									<li
										key={attachment.id}
										className="relative size-16 overflow-hidden rounded-lg border border-border/8"
									>
										<img
											src={attachment.dataUrl}
											alt={attachment.name}
											className="size-full object-cover"
										/>
										<Button
											variant="ghost"
											size="icon-xs"
											onClick={() => removeAttachment(index)}
											aria-label={t("settings.bugReport.removeImage", {
												name: attachment.name,
											})}
											className="absolute inset-e-0.5 top-0.5 bg-surface/80"
										>
											<HugeiconsIcon
												icon={Cancel01Icon}
												strokeWidth={2}
												className="size-3"
											/>
										</Button>
									</li>
								))}
							</ul>
						)}
						<div className="flex items-center gap-2">
							<Button
								variant="outline"
								size="sm"
								onClick={() => fileInputRef.current?.click()}
								disabled={attachments.length >= MAX_ATTACHMENTS}
								className="gap-2"
							>
								<HugeiconsIcon
									icon={Image01Icon}
									strokeWidth={2}
									className="h-4 w-4"
								/>
								{t("settings.bugReport.addImages")}
							</Button>
							<span className="text-xs text-muted-foreground">
								{t("settings.bugReport.attachmentsHint", {
									count: String(MAX_ATTACHMENTS),
								})}
							</span>
						</div>
						<input
							ref={fileInputRef}
							type="file"
							accept="image/*"
							multiple
							className="hidden"
							onChange={(e) => {
								void addFiles(e.target.files);
								// Reset so re-picking the same file still fires change.
								e.target.value = "";
							}}
						/>
					</div>
				</div>

				{/* What the report will carry, shown before sending so the user
				    is never surprised by what leaves their machine. */}
				<div className="flex flex-col gap-1 rounded-lg bg-surface-subtle px-3 py-2">
					<span className="text-xs font-medium text-foreground">
						{t("settings.bugReport.contextLabel")}
					</span>
					{collectReportContext(APP_VERSION).map((line) => (
						<span
							key={line}
							className="font-mono text-xs text-muted-foreground"
						>
							{line}
						</span>
					))}
				</div>

				<ModalFooter>
					<Button variant="outline" onClick={onClose} disabled={sending}>
						{t("common.cancel")}
					</Button>
					<Button onClick={handleSend} disabled={!canSend} className="gap-2">
						<HugeiconsIcon
							icon={SentIcon}
							strokeWidth={2}
							className="h-4 w-4"
						/>
						{sending
							? t("settings.bugReport.sending")
							: t("settings.bugReport.send")}
					</Button>
				</ModalFooter>
			</div>
		</Modal>
	);
}

export const BugReportModal = memo(BugReportModalInner);
