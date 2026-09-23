import { useState } from "react";

import type { SendersView } from "@/api/generated/dashboard";
import { Button } from "@/components/Button/Button";

import { NumbersSection } from "../NumbersSection";
import { countryOptions, enabledCountriesOf, sendersOf } from "../rules";
import { AlphaTagsTable } from "./AlphaTagsTable";
import { RegisterAlphaTagModal } from "./RegisterAlphaTagModal";
import { emptyAlphaTag } from "./rules";

const ADD_LABEL = "+ Add";
const COPY = "Create unique sender names to brand your messages.";
const FALLBACK_COUNTRY = "GB";

interface Props {
  view: SendersView;
}

export function AlphaTagsTab({ view }: Props) {
  const [registering, setRegistering] = useState(false);
  const [defaultCountry = FALLBACK_COUNTRY] = enabledCountriesOf(view);

  return (
    <NumbersSection
      action={
        <Button
          onClick={() => {
            setRegistering(true);
          }}
        >
          {ADD_LABEL}
        </Button>
      }
      copy={COPY}
      title="Alpha Tags"
    >
      <AlphaTagsTable rows={sendersOf(view, "ALPHA")} />
      {registering ? (
        <RegisterAlphaTagModal
          countries={countryOptions(enabledCountriesOf(view))}
          initial={emptyAlphaTag(defaultCountry)}
          onClose={() => {
            setRegistering(false);
          }}
          onRegistered={() => {
            setRegistering(false);
          }}
        />
      ) : null}
    </NumbersSection>
  );
}
