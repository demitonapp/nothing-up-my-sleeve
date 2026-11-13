// Sending the book to a Kindle (13 November, Justin: the latest epub is something a visitor can "email to their
// kindle"). A web page cannot attach a file to an email, and the public site has no server to send one from, so
// this is two honest steps: the visitor downloads the file, then their own mail app opens addressed to their
// Kindle and they attach it. Amazon's own Send to Kindle page is offered beside it for anyone who would rather
// drop the file there. The Kindle address stays in this browser, and only if the visitor asks for that.

import { useEffect, useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { btnCls, checkCls, fieldCls } from '@/lib/ui';
import { BOOK, SEND_TO_KINDLE, kindleAddress, megabytes, rememberKindle } from '@/lib/firstCards';

export default function KindleDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [address, setAddress] = useState('');
  const [keep, setKeep] = useState(false);
  const [downloaded, setDownloaded] = useState(false);

  useEffect(() => {
    if (!open) return;
    const had = kindleAddress();
    setAddress(had);
    setKeep(!!had);
    setDownloaded(false);
  }, [open]);

  const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(address.trim());
  const mailto = `mailto:${encodeURIComponent(address.trim())}?subject=${encodeURIComponent(`${BOOK.title} (${BOOK.version})`)}`;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="kindledialog sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Send it to your Kindle</DialogTitle>
          <DialogDescription>
            A web page cannot attach a file to an email, so this takes two steps. The book goes from your own email to your own Kindle; this site sends nothing and keeps nothing.
          </DialogDescription>
        </DialogHeader>

        <ol className="kindlesteps">
          <li>
            <b>Download the book.</b>
            <a className={btnCls(downloaded ? 'outline' : 'default', 'mt-1')} href={BOOK.file} download={BOOK.downloadName} onClick={() => setDownloaded(true)}>
              {downloaded ? 'Downloaded' : `Download the epub (${megabytes(BOOK.bytes)})`}
            </a>
          </li>
          <li>
            <b>Email it to your Kindle.</b>
            <label className="kindlefield">
              <span>Your Kindle's email address</span>
              <input
                className={fieldCls('w-full')}
                type="email"
                inputMode="email"
                autoComplete="off"
                placeholder="name@kindle.com"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
              />
            </label>
            <label className="kindlekeep">
              <input className={checkCls()} type="checkbox" checked={keep} onChange={(e) => { setKeep(e.target.checked); if (!e.target.checked) rememberKindle(null); }} />
              <span>Remember this address in this browser</span>
            </label>
            <a
              className={btnCls('default', valid ? '' : 'pointer-events-none opacity-50')}
              href={valid ? mailto : undefined}
              aria-disabled={!valid}
              onClick={() => { if (valid) rememberKindle(keep ? address.trim() : null); }}
            >
              Open my email
            </a>
            <span className="kindlenote">Attach the file you downloaded, then send. No message is needed.</span>
          </li>
        </ol>

        <p className="kindlenote">
          Amazon only delivers mail from an address on your approved list: on Amazon, open Manage Your Content and Devices, then Preferences, then Personal Document Settings, where your Kindle's address is also shown.
          Or skip email and drop the file on <a href={SEND_TO_KINDLE} target="_blank" rel="noreferrer">Amazon's Send to Kindle page</a>.
        </p>
      </DialogContent>
    </Dialog>
  );
}
