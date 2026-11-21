"""Generate the consolidated, deterministic third-party notices artifact.

Reads installed distribution metadata and the checked-in lockfiles read-only.
No network access, no new dependencies, no writes to any input. The only file
this script writes is ``docs/THIRD_PARTY_NOTICES.md`` between its markers, so
the hand-written FFmpeg/PyAV sections survive regeneration byte-for-byte.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]
NOTICE = ROOT / "docs" / "THIRD_PARTY_NOTICES.md"
REQUIREMENTS_LOCK = ROOT / "requirements-lock.txt"
PACKAGE_LOCK = ROOT / "voice_typer" / "client" / "package-lock.json"
CARGO_LOCK = ROOT / "src-tauri" / "Cargo.lock"
VENV = ROOT / ".venv"

BEGIN = "<!-- BEGIN GENERATED THIRD-PARTY NOTICES -->"
END = "<!-- END GENERATED THIRD-PARTY NOTICES -->"

FULL_TEXT_LICENSES = frozenset(
    {"MIT", "BSD-3-Clause", "Apache-2.0", "ISC", "MPL-2.0", "OFL-1.1", "Unicode-3.0", "CC-BY-4.0"}
)
TEXT_SOURCE = {
    "MIT": "react 19.2.7 LICENSE (canonical MIT body)",
    "BSD-3-Clause": "av 17.1.0 LICENSE.txt (canonical BSD-3-Clause body)",
    "Apache-2.0": "hf-xet 1.6.0 LICENSE (full Apache License 2.0)",
    "ISC": "d3-array 3.2.4 LICENSE (canonical ISC body)",
    "MPL-2.0": "cssparser 0.37.0 LICENSE (full MPL 2.0)",
    "OFL-1.1": "LICENSES.chromium.html SIL Open Font License 1.1 section",
    "Unicode-3.0": "icu_collections 2.2.0 LICENSE (Unicode License V3)",
    "CC-BY-4.0": "caniuse-lite LICENSE (Attribution 4.0 International)",
}

# Frozen canonical license texts. Each distinct text appears ONCE in the
# artifact; components reference it by the ``group`` field below. The eight
# permissive/copyleft bodies are verbatim from locally installed license files
# (see TEXT_SOURCE); identifiers without a local full text get an explicit
# UNVERIFIED pointer instead of an invented body.
LICENSE_TEXTS: dict[str, str] = {
    "0BSD": (
        "No full license-text file was found in the installed Windows output for this identifier. Marked "
        "UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: "
        "https://opensource.org/license/0bsd.\n"
    ),
    "Apache-2.0": (
        "Apache License\n"
        "                           Version 2.0, January 2004\n"
        "                        http://www.apache.org/licenses/\n"
        "\n"
        "   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION\n"
        "\n"
        "   1. Definitions.\n"
        "\n"
        "      \"License\" shall mean the terms and conditions for use, reproduction,\n"
        "      and distribution as defined by Sections 1 through 9 of this document.\n"
        "\n"
        "      \"Licensor\" shall mean the copyright owner or entity authorized by\n"
        "      the copyright owner that is granting the License.\n"
        "\n"
        "      \"Legal Entity\" shall mean the union of the acting entity and all\n"
        "      other entities that control, are controlled by, or are under common\n"
        "      control with that entity. For the purposes of this definition,\n"
        "      \"control\" means (i) the power, direct or indirect, to cause the\n"
        "      direction or management of such entity, whether by contract or\n"
        "      otherwise, or (ii) ownership of fifty percent (50%) or more of the\n"
        "      outstanding shares, or (iii) beneficial ownership of such entity.\n"
        "\n"
        "      \"You\" (or \"Your\") shall mean an individual or Legal Entity\n"
        "      exercising permissions granted by this License.\n"
        "\n"
        "      \"Source\" form shall mean the preferred form for making modifications,\n"
        "      including but not limited to software source code, documentation\n"
        "      source, and configuration files.\n"
        "\n"
        "      \"Object\" form shall mean any form resulting from mechanical\n"
        "      transformation or translation of a Source form, including but\n"
        "      not limited to compiled object code, generated documentation,\n"
        "      and conversions to other media types.\n"
        "\n"
        "      \"Work\" shall mean the work of authorship, whether in Source or\n"
        "      Object form, made available under the License, as indicated by a\n"
        "      copyright notice that is included in or attached to the work\n"
        "      (an example is provided in the Appendix below).\n"
        "\n"
        "      \"Derivative Works\" shall mean any work, whether in Source or Object\n"
        "      form, that is based on (or derived from) the Work and for which the\n"
        "      editorial revisions, annotations, elaborations, or other modifications\n"
        "      represent, as a whole, an original work of authorship. For the purposes\n"
        "      of this License, Derivative Works shall not include works that remain\n"
        "      separable from, or merely link (or bind by name) to the interfaces of,\n"
        "      the Work and Derivative Works thereof.\n"
        "\n"
        "      \"Contribution\" shall mean any work of authorship, including\n"
        "      the original version of the Work and any modifications or additions\n"
        "      to that Work or Derivative Works thereof, that is intentionally\n"
        "      submitted to Licensor for inclusion in the Work by the copyright owner\n"
        "      or by an individual or Legal Entity authorized to submit on behalf of\n"
        "      the copyright owner. For the purposes of this definition, \"submitted\"\n"
        "      means any form of electronic, verbal, or written communication sent\n"
        "      to the Licensor or its representatives, including but not limited to\n"
        "      communication on electronic mailing lists, source code control systems,\n"
        "      and issue tracking systems that are managed by, or on behalf of, the\n"
        "      Licensor for the purpose of discussing and improving the Work, but\n"
        "      excluding communication that is conspicuously marked or otherwise\n"
        "      designated in writing by the copyright owner as \"Not a Contribution.\"\n"
        "\n"
        "      \"Contributor\" shall mean Licensor and any individual or Legal Entity\n"
        "      on behalf of whom a Contribution has been received by Licensor and\n"
        "      subsequently incorporated within the Work.\n"
        "\n"
        "   2. Grant of Copyright License. Subject to the terms and conditions of\n"
        "      this License, each Contributor hereby grants to You a perpetual,\n"
        "      worldwide, non-exclusive, no-charge, royalty-free, irrevocable\n"
        "      copyright license to reproduce, prepare Derivative Works of,\n"
        "      publicly display, publicly perform, sublicense, and distribute the\n"
        "      Work and such Derivative Works in Source or Object form.\n"
        "\n"
        "   3. Grant of Patent License. Subject to the terms and conditions of\n"
        "      this License, each Contributor hereby grants to You a perpetual,\n"
        "      worldwide, non-exclusive, no-charge, royalty-free, irrevocable\n"
        "      (except as stated in this section) patent license to make, have made,\n"
        "      use, offer to sell, sell, import, and otherwise transfer the Work,\n"
        "      where such license applies only to those patent claims licensable\n"
        "      by such Contributor that are necessarily infringed by their\n"
        "      Contribution(s) alone or by combination of their Contribution(s)\n"
        "      with the Work to which such Contribution(s) was submitted. If You\n"
        "      institute patent litigation against any entity (including a\n"
        "      cross-claim or counterclaim in a lawsuit) alleging that the Work\n"
        "      or a Contribution incorporated within the Work constitutes direct\n"
        "      or contributory patent infringement, then any patent licenses\n"
        "      granted to You under this License for that Work shall terminate\n"
        "      as of the date such litigation is filed.\n"
        "\n"
        "   4. Redistribution. You may reproduce and distribute copies of the\n"
        "      Work or Derivative Works thereof in any medium, with or without\n"
        "      modifications, and in Source or Object form, provided that You\n"
        "      meet the following conditions:\n"
        "\n"
        "      (a) You must give any other recipients of the Work or\n"
        "          Derivative Works a copy of this License; and\n"
        "\n"
        "      (b) You must cause any modified files to carry prominent notices\n"
        "          stating that You changed the files; and\n"
        "\n"
        "      (c) You must retain, in the Source form of any Derivative Works\n"
        "          that You distribute, all copyright, patent, trademark, and\n"
        "          attribution notices from the Source form of the Work,\n"
        "          excluding those notices that do not pertain to any part of\n"
        "          the Derivative Works; and\n"
        "\n"
        "      (d) If the Work includes a \"NOTICE\" text file as part of its\n"
        "          distribution, then any Derivative Works that You distribute must\n"
        "          include a readable copy of the attribution notices contained\n"
        "          within such NOTICE file, excluding those notices that do not\n"
        "          pertain to any part of the Derivative Works, in at least one\n"
        "          of the following places: within a NOTICE text file distributed\n"
        "          as part of the Derivative Works; within the Source form or\n"
        "          documentation, if provided along with the Derivative Works; or,\n"
        "          within a display generated by the Derivative Works, if and\n"
        "          wherever such third-party notices normally appear. The contents\n"
        "          of the NOTICE file are for informational purposes only and\n"
        "          do not modify the License. You may add Your own attribution\n"
        "          notices within Derivative Works that You distribute, alongside\n"
        "          or as an addendum to the NOTICE text from the Work, provided\n"
        "          that such additional attribution notices cannot be construed\n"
        "          as modifying the License.\n"
        "\n"
        "      You may add Your own copyright statement to Your modifications and\n"
        "      may provide additional or different license terms and conditions\n"
        "      for use, reproduction, or distribution of Your modifications, or\n"
        "      for any such Derivative Works as a whole, provided Your use,\n"
        "      reproduction, and distribution of the Work otherwise complies with\n"
        "      the conditions stated in this License.\n"
        "\n"
        "   5. Submission of Contributions. Unless You explicitly state otherwise,\n"
        "      any Contribution intentionally submitted for inclusion in the Work\n"
        "      by You to the Licensor shall be under the terms and conditions of\n"
        "      this License, without any additional terms or conditions.\n"
        "      Notwithstanding the above, nothing herein shall supersede or modify\n"
        "      the terms of any separate license agreement you may have executed\n"
        "      with Licensor regarding such Contributions.\n"
        "\n"
        "   6. Trademarks. This License does not grant permission to use the trade\n"
        "      names, trademarks, service marks, or product names of the Licensor,\n"
        "      except as required for reasonable and customary use in describing the\n"
        "      origin of the Work and reproducing the content of the NOTICE file.\n"
        "\n"
        "   7. Disclaimer of Warranty. Unless required by applicable law or\n"
        "      agreed to in writing, Licensor provides the Work (and each\n"
        "      Contributor provides its Contributions) on an \"AS IS\" BASIS,\n"
        "      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or\n"
        "      implied, including, without limitation, any warranties or conditions\n"
        "      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A\n"
        "      PARTICULAR PURPOSE. You are solely responsible for determining the\n"
        "      appropriateness of using or redistributing the Work and assume any\n"
        "      risks associated with Your exercise of permissions under this License.\n"
        "\n"
        "   8. Limitation of Liability. In no event and under no legal theory,\n"
        "      whether in tort (including negligence), contract, or otherwise,\n"
        "      unless required by applicable law (such as deliberate and grossly\n"
        "      negligent acts) or agreed to in writing, shall any Contributor be\n"
        "      liable to You for damages, including any direct, indirect, special,\n"
        "      incidental, or consequential damages of any character arising as a\n"
        "      result of this License or out of the use or inability to use the\n"
        "      Work (including but not limited to damages for loss of goodwill,\n"
        "      work stoppage, computer failure or malfunction, or any and all\n"
        "      other commercial damages or losses), even if such Contributor\n"
        "      has been advised of the possibility of such damages.\n"
        "\n"
        "   9. Accepting Warranty or Additional Liability. While redistributing\n"
        "      the Work or Derivative Works thereof, You may choose to offer,\n"
        "      and charge a fee for, acceptance of support, warranty, indemnity,\n"
        "      or other liability obligations and/or rights consistent with this\n"
        "      License. However, in accepting such obligations, You may act only\n"
        "      on Your own behalf and on Your sole responsibility, not on behalf\n"
        "      of any other Contributor, and only if You agree to indemnify,\n"
        "      defend, and hold each Contributor harmless for any liability\n"
        "      incurred by, or claims asserted against, such Contributor by reason\n"
        "      of your accepting any such warranty or additional liability.\n"
        "\n"
        "   END OF TERMS AND CONDITIONS\n"
        "\n"
        "   APPENDIX: How to apply the Apache License to your work.\n"
        "\n"
        "      To apply the Apache License to your work, attach the following\n"
        "      boilerplate notice, with the fields enclosed by brackets \"[]\"\n"
        "      replaced with your own identifying information. (Don't include\n"
        "      the brackets!)  The text should be enclosed in the appropriate\n"
        "      comment syntax for the file format. We also recommend that a\n"
        "      file or class name and description of purpose be included on the\n"
        "      same \"printed page\" as the copyright notice for easier\n"
        "      identification within third-party archives.\n"
        "\n"
        "   Copyright [yyyy] [name of copyright owner]\n"
        "\n"
        "   Licensed under the Apache License, Version 2.0 (the \"License\");\n"
        "   you may not use this file except in compliance with the License.\n"
        "   You may obtain a copy of the License at\n"
        "\n"
        "       http://www.apache.org/licenses/LICENSE-2.0\n"
        "\n"
        "   Unless required by applicable law or agreed to in writing, software\n"
        "   distributed under the License is distributed on an \"AS IS\" BASIS,\n"
        "   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n"
        "   See the License for the specific language governing permissions and\n"
        "   limitations under the License.\n"
    ),
    "BSD-2-Clause": (
        "No full license-text file was found in the installed Windows output for this identifier. Marked "
        "UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: "
        "https://opensource.org/license/bsd-2-clause.\n"
    ),
    "BSD-3-Clause": (
        "Copyright retained by original committers. All rights reserved.\n"
        "\n"
        "Redistribution and use in source and binary forms, with or without\n"
        "modification, are permitted provided that the following conditions are met:\n"
        "    * Redistributions of source code must retain the above copyright\n"
        "      notice, this list of conditions and the following disclaimer.\n"
        "    * Redistributions in binary form must reproduce the above copyright\n"
        "      notice, this list of conditions and the following disclaimer in the\n"
        "      documentation and/or other materials provided with the distribution.\n"
        "    * Neither the name of the project nor the names of its contributors may be\n"
        "      used to endorse or promote products derived from this software without\n"
        "      specific prior written permission.\n"
        "\n"
        "THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS \"AS IS\"\n"
        "AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE\n"
        "IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE\n"
        "DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDERS BE LIABLE FOR ANY DIRECT,\n"
        "INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,\n"
        "BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,\n"
        "DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY\n"
        "OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING\n"
        "NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,\n"
        "EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.\n"
    ),
    "CC-BY-4.0": (
        "Attribution 4.0 International\n"
        "\n"
        "=======================================================================\n"
        "\n"
        "Creative Commons Corporation (\"Creative Commons\") is not a law firm and\n"
        "does not provide legal services or legal advice. Distribution of\n"
        "Creative Commons public licenses does not create a lawyer-client or\n"
        "other relationship. Creative Commons makes its licenses and related\n"
        "information available on an \"as-is\" basis. Creative Commons gives no\n"
        "warranties regarding its licenses, any material licensed under their\n"
        "terms and conditions, or any related information. Creative Commons\n"
        "disclaims all liability for damages resulting from their use to the\n"
        "fullest extent possible.\n"
        "\n"
        "Using Creative Commons Public Licenses\n"
        "\n"
        "Creative Commons public licenses provide a standard set of terms and\n"
        "conditions that creators and other rights holders may use to share\n"
        "original works of authorship and other material subject to copyright\n"
        "and certain other rights specified in the public license below. The\n"
        "following considerations are for informational purposes only, are not\n"
        "exhaustive, and do not form part of our licenses.\n"
        "\n"
        "     Considerations for licensors: Our public licenses are\n"
        "     intended for use by those authorized to give the public\n"
        "     permission to use material in ways otherwise restricted by\n"
        "     copyright and certain other rights. Our licenses are\n"
        "     irrevocable. Licensors should read and understand the terms\n"
        "     and conditions of the license they choose before applying it.\n"
        "     Licensors should also secure all rights necessary before\n"
        "     applying our licenses so that the public can reuse the\n"
        "     material as expected. Licensors should clearly mark any\n"
        "     material not subject to the license. This includes other CC-\n"
        "     licensed material, or material used under an exception or\n"
        "     limitation to copyright. More considerations for licensors:\n"
        "\twiki.creativecommons.org/Considerations_for_licensors\n"
        "\n"
        "     Considerations for the public: By using one of our public\n"
        "     licenses, a licensor grants the public permission to use the\n"
        "     licensed material under specified terms and conditions. If\n"
        "     the licensor's permission is not necessary for any reason--for\n"
        "     example, because of any applicable exception or limitation to\n"
        "     copyright--then that use is not regulated by the license. Our\n"
        "     licenses grant only permissions under copyright and certain\n"
        "     other rights that a licensor has authority to grant. Use of\n"
        "     the licensed material may still be restricted for other\n"
        "     reasons, including because others have copyright or other\n"
        "     rights in the material. A licensor may make special requests,\n"
        "     such as asking that all changes be marked or described.\n"
        "     Although not required by our licenses, you are encouraged to\n"
        "     respect those requests where reasonable. More_considerations\n"
        "     for the public: \n"
        "\twiki.creativecommons.org/Considerations_for_licensees\n"
        "\n"
        "=======================================================================\n"
        "\n"
        "Creative Commons Attribution 4.0 International Public License\n"
        "\n"
        "By exercising the Licensed Rights (defined below), You accept and agree\n"
        "to be bound by the terms and conditions of this Creative Commons\n"
        "Attribution 4.0 International Public License (\"Public License\"). To the\n"
        "extent this Public License may be interpreted as a contract, You are\n"
        "granted the Licensed Rights in consideration of Your acceptance of\n"
        "these terms and conditions, and the Licensor grants You such rights in\n"
        "consideration of benefits the Licensor receives from making the\n"
        "Licensed Material available under these terms and conditions.\n"
        "\n"
        "\n"
        "Section 1 -- Definitions.\n"
        "\n"
        "  a. Adapted Material means material subject to Copyright and Similar\n"
        "     Rights that is derived from or based upon the Licensed Material\n"
        "     and in which the Licensed Material is translated, altered,\n"
        "     arranged, transformed, or otherwise modified in a manner requiring\n"
        "     permission under the Copyright and Similar Rights held by the\n"
        "     Licensor. For purposes of this Public License, where the Licensed\n"
        "     Material is a musical work, performance, or sound recording,\n"
        "     Adapted Material is always produced where the Licensed Material is\n"
        "     synched in timed relation with a moving image.\n"
        "\n"
        "  b. Adapter's License means the license You apply to Your Copyright\n"
        "     and Similar Rights in Your contributions to Adapted Material in\n"
        "     accordance with the terms and conditions of this Public License.\n"
        "\n"
        "  c. Copyright and Similar Rights means copyright and/or similar rights\n"
        "     closely related to copyright including, without limitation,\n"
        "     performance, broadcast, sound recording, and Sui Generis Database\n"
        "     Rights, without regard to how the rights are labeled or\n"
        "     categorized. For purposes of this Public License, the rights\n"
        "     specified in Section 2(b)(1)-(2) are not Copyright and Similar\n"
        "     Rights.\n"
        "\n"
        "  d. Effective Technological Measures means those measures that, in the\n"
        "     absence of proper authority, may not be circumvented under laws\n"
        "     fulfilling obligations under Article 11 of the WIPO Copyright\n"
        "     Treaty adopted on December 20, 1996, and/or similar international\n"
        "     agreements.\n"
        "\n"
        "  e. Exceptions and Limitations means fair use, fair dealing, and/or\n"
        "     any other exception or limitation to Copyright and Similar Rights\n"
        "     that applies to Your use of the Licensed Material.\n"
        "\n"
        "  f. Licensed Material means the artistic or literary work, database,\n"
        "     or other material to which the Licensor applied this Public\n"
        "     License.\n"
        "\n"
        "  g. Licensed Rights means the rights granted to You subject to the\n"
        "     terms and conditions of this Public License, which are limited to\n"
        "     all Copyright and Similar Rights that apply to Your use of the\n"
        "     Licensed Material and that the Licensor has authority to license.\n"
        "\n"
        "  h. Licensor means the individual(s) or entity(ies) granting rights\n"
        "     under this Public License.\n"
        "\n"
        "  i. Share means to provide material to the public by any means or\n"
        "     process that requires permission under the Licensed Rights, such\n"
        "     as reproduction, public display, public performance, distribution,\n"
        "     dissemination, communication, or importation, and to make material\n"
        "     available to the public including in ways that members of the\n"
        "     public may access the material from a place and at a time\n"
        "     individually chosen by them.\n"
        "\n"
        "  j. Sui Generis Database Rights means rights other than copyright\n"
        "     resulting from Directive 96/9/EC of the European Parliament and of\n"
        "     the Council of 11 March 1996 on the legal protection of databases,\n"
        "     as amended and/or succeeded, as well as other essentially\n"
        "     equivalent rights anywhere in the world.\n"
        "\n"
        "  k. You means the individual or entity exercising the Licensed Rights\n"
        "     under this Public License. Your has a corresponding meaning.\n"
        "\n"
        "\n"
        "Section 2 -- Scope.\n"
        "\n"
        "  a. License grant.\n"
        "\n"
        "       1. Subject to the terms and conditions of this Public License,\n"
        "          the Licensor hereby grants You a worldwide, royalty-free,\n"
        "          non-sublicensable, non-exclusive, irrevocable license to\n"
        "          exercise the Licensed Rights in the Licensed Material to:\n"
        "\n"
        "            a. reproduce and Share the Licensed Material, in whole or\n"
        "               in part; and\n"
        "\n"
        "            b. produce, reproduce, and Share Adapted Material.\n"
        "\n"
        "       2. Exceptions and Limitations. For the avoidance of doubt, where\n"
        "          Exceptions and Limitations apply to Your use, this Public\n"
        "          License does not apply, and You do not need to comply with\n"
        "          its terms and conditions.\n"
        "\n"
        "       3. Term. The term of this Public License is specified in Section\n"
        "          6(a).\n"
        "\n"
        "       4. Media and formats; technical modifications allowed. The\n"
        "          Licensor authorizes You to exercise the Licensed Rights in\n"
        "          all media and formats whether now known or hereafter created,\n"
        "          and to make technical modifications necessary to do so. The\n"
        "          Licensor waives and/or agrees not to assert any right or\n"
        "          authority to forbid You from making technical modifications\n"
        "          necessary to exercise the Licensed Rights, including\n"
        "          technical modifications necessary to circumvent Effective\n"
        "          Technological Measures. For purposes of this Public License,\n"
        "          simply making modifications authorized by this Section 2(a)\n"
        "          (4) never produces Adapted Material.\n"
        "\n"
        "       5. Downstream recipients.\n"
        "\n"
        "            a. Offer from the Licensor -- Licensed Material. Every\n"
        "               recipient of the Licensed Material automatically\n"
        "               receives an offer from the Licensor to exercise the\n"
        "               Licensed Rights under the terms and conditions of this\n"
        "               Public License.\n"
        "\n"
        "            b. No downstream restrictions. You may not offer or impose\n"
        "               any additional or different terms or conditions on, or\n"
        "               apply any Effective Technological Measures to, the\n"
        "               Licensed Material if doing so restricts exercise of the\n"
        "               Licensed Rights by any recipient of the Licensed\n"
        "               Material.\n"
        "\n"
        "       6. No endorsement. Nothing in this Public License constitutes or\n"
        "          may be construed as permission to assert or imply that You\n"
        "          are, or that Your use of the Licensed Material is, connected\n"
        "          with, or sponsored, endorsed, or granted official status by,\n"
        "          the Licensor or others designated to receive attribution as\n"
        "          provided in Section 3(a)(1)(A)(i).\n"
        "\n"
        "  b. Other rights.\n"
        "\n"
        "       1. Moral rights, such as the right of integrity, are not\n"
        "          licensed under this Public License, nor are publicity,\n"
        "          privacy, and/or other similar personality rights; however, to\n"
        "          the extent possible, the Licensor waives and/or agrees not to\n"
        "          assert any such rights held by the Licensor to the limited\n"
        "          extent necessary to allow You to exercise the Licensed\n"
        "          Rights, but not otherwise.\n"
        "\n"
        "       2. Patent and trademark rights are not licensed under this\n"
        "          Public License.\n"
        "\n"
        "       3. To the extent possible, the Licensor waives any right to\n"
        "          collect royalties from You for the exercise of the Licensed\n"
        "          Rights, whether directly or through a collecting society\n"
        "          under any voluntary or waivable statutory or compulsory\n"
        "          licensing scheme. In all other cases the Licensor expressly\n"
        "          reserves any right to collect such royalties.\n"
        "\n"
        "\n"
        "Section 3 -- License Conditions.\n"
        "\n"
        "Your exercise of the Licensed Rights is expressly made subject to the\n"
        "following conditions.\n"
        "\n"
        "  a. Attribution.\n"
        "\n"
        "       1. If You Share the Licensed Material (including in modified\n"
        "          form), You must:\n"
        "\n"
        "            a. retain the following if it is supplied by the Licensor\n"
        "               with the Licensed Material:\n"
        "\n"
        "                 i. identification of the creator(s) of the Licensed\n"
        "                    Material and any others designated to receive\n"
        "                    attribution, in any reasonable manner requested by\n"
        "                    the Licensor (including by pseudonym if\n"
        "                    designated);\n"
        "\n"
        "                ii. a copyright notice;\n"
        "\n"
        "               iii. a notice that refers to this Public License;\n"
        "\n"
        "                iv. a notice that refers to the disclaimer of\n"
        "                    warranties;\n"
        "\n"
        "                 v. a URI or hyperlink to the Licensed Material to the\n"
        "                    extent reasonably practicable;\n"
        "\n"
        "            b. indicate if You modified the Licensed Material and\n"
        "               retain an indication of any previous modifications; and\n"
        "\n"
        "            c. indicate the Licensed Material is licensed under this\n"
        "               Public License, and include the text of, or the URI or\n"
        "               hyperlink to, this Public License.\n"
        "\n"
        "       2. You may satisfy the conditions in Section 3(a)(1) in any\n"
        "          reasonable manner based on the medium, means, and context in\n"
        "          which You Share the Licensed Material. For example, it may be\n"
        "          reasonable to satisfy the conditions by providing a URI or\n"
        "          hyperlink to a resource that includes the required\n"
        "          information.\n"
        "\n"
        "       3. If requested by the Licensor, You must remove any of the\n"
        "          information required by Section 3(a)(1)(A) to the extent\n"
        "          reasonably practicable.\n"
        "\n"
        "       4. If You Share Adapted Material You produce, the Adapter's\n"
        "          License You apply must not prevent recipients of the Adapted\n"
        "          Material from complying with this Public License.\n"
        "\n"
        "\n"
        "Section 4 -- Sui Generis Database Rights.\n"
        "\n"
        "Where the Licensed Rights include Sui Generis Database Rights that\n"
        "apply to Your use of the Licensed Material:\n"
        "\n"
        "  a. for the avoidance of doubt, Section 2(a)(1) grants You the right\n"
        "     to extract, reuse, reproduce, and Share all or a substantial\n"
        "     portion of the contents of the database;\n"
        "\n"
        "  b. if You include all or a substantial portion of the database\n"
        "     contents in a database in which You have Sui Generis Database\n"
        "     Rights, then the database in which You have Sui Generis Database\n"
        "     Rights (but not its individual contents) is Adapted Material; and\n"
        "\n"
        "  c. You must comply with the conditions in Section 3(a) if You Share\n"
        "     all or a substantial portion of the contents of the database.\n"
        "\n"
        "For the avoidance of doubt, this Section 4 supplements and does not\n"
        "replace Your obligations under this Public License where the Licensed\n"
        "Rights include other Copyright and Similar Rights.\n"
        "\n"
        "\n"
        "Section 5 -- Disclaimer of Warranties and Limitation of Liability.\n"
        "\n"
        "  a. UNLESS OTHERWISE SEPARATELY UNDERTAKEN BY THE LICENSOR, TO THE\n"
        "     EXTENT POSSIBLE, THE LICENSOR OFFERS THE LICENSED MATERIAL AS-IS\n"
        "     AND AS-AVAILABLE, AND MAKES NO REPRESENTATIONS OR WARRANTIES OF\n"
        "     ANY KIND CONCERNING THE LICENSED MATERIAL, WHETHER EXPRESS,\n"
        "     IMPLIED, STATUTORY, OR OTHER. THIS INCLUDES, WITHOUT LIMITATION,\n"
        "     WARRANTIES OF TITLE, MERCHANTABILITY, FITNESS FOR A PARTICULAR\n"
        "     PURPOSE, NON-INFRINGEMENT, ABSENCE OF LATENT OR OTHER DEFECTS,\n"
        "     ACCURACY, OR THE PRESENCE OR ABSENCE OF ERRORS, WHETHER OR NOT\n"
        "     KNOWN OR DISCOVERABLE. WHERE DISCLAIMERS OF WARRANTIES ARE NOT\n"
        "     ALLOWED IN FULL OR IN PART, THIS DISCLAIMER MAY NOT APPLY TO YOU.\n"
        "\n"
        "  b. TO THE EXTENT POSSIBLE, IN NO EVENT WILL THE LICENSOR BE LIABLE\n"
        "     TO YOU ON ANY LEGAL THEORY (INCLUDING, WITHOUT LIMITATION,\n"
        "     NEGLIGENCE) OR OTHERWISE FOR ANY DIRECT, SPECIAL, INDIRECT,\n"
        "     INCIDENTAL, CONSEQUENTIAL, PUNITIVE, EXEMPLARY, OR OTHER LOSSES,\n"
        "     COSTS, EXPENSES, OR DAMAGES ARISING OUT OF THIS PUBLIC LICENSE OR\n"
        "     USE OF THE LICENSED MATERIAL, EVEN IF THE LICENSOR HAS BEEN\n"
        "     ADVISED OF THE POSSIBILITY OF SUCH LOSSES, COSTS, EXPENSES, OR\n"
        "     DAMAGES. WHERE A LIMITATION OF LIABILITY IS NOT ALLOWED IN FULL OR\n"
        "     IN PART, THIS LIMITATION MAY NOT APPLY TO YOU.\n"
        "\n"
        "  c. The disclaimer of warranties and limitation of liability provided\n"
        "     above shall be interpreted in a manner that, to the extent\n"
        "     possible, most closely approximates an absolute disclaimer and\n"
        "     waiver of all liability.\n"
        "\n"
        "\n"
        "Section 6 -- Term and Termination.\n"
        "\n"
        "  a. This Public License applies for the term of the Copyright and\n"
        "     Similar Rights licensed here. However, if You fail to comply with\n"
        "     this Public License, then Your rights under this Public License\n"
        "     terminate automatically.\n"
        "\n"
        "  b. Where Your right to use the Licensed Material has terminated under\n"
        "     Section 6(a), it reinstates:\n"
        "\n"
        "       1. automatically as of the date the violation is cured, provided\n"
        "          it is cured within 30 days of Your discovery of the\n"
        "          violation; or\n"
        "\n"
        "       2. upon express reinstatement by the Licensor.\n"
        "\n"
        "     For the avoidance of doubt, this Section 6(b) does not affect any\n"
        "     right the Licensor may have to seek remedies for Your violations\n"
        "     of this Public License.\n"
        "\n"
        "  c. For the avoidance of doubt, the Licensor may also offer the\n"
        "     Licensed Material under separate terms or conditions or stop\n"
        "     distributing the Licensed Material at any time; however, doing so\n"
        "     will not terminate this Public License.\n"
        "\n"
        "  d. Sections 1, 5, 6, 7, and 8 survive termination of this Public\n"
        "     License.\n"
        "\n"
        "\n"
        "Section 7 -- Other Terms and Conditions.\n"
        "\n"
        "  a. The Licensor shall not be bound by any additional or different\n"
        "     terms or conditions communicated by You unless expressly agreed.\n"
        "\n"
        "  b. Any arrangements, understandings, or agreements regarding the\n"
        "     Licensed Material not stated herein are separate from and\n"
        "     independent of the terms and conditions of this Public License.\n"
        "\n"
        "\n"
        "Section 8 -- Interpretation.\n"
        "\n"
        "  a. For the avoidance of doubt, this Public License does not, and\n"
        "     shall not be interpreted to, reduce, limit, restrict, or impose\n"
        "     conditions on any use of the Licensed Material that could lawfully\n"
        "     be made without permission under this Public License.\n"
        "\n"
        "  b. To the extent possible, if any provision of this Public License is\n"
        "     deemed unenforceable, it shall be automatically reformed to the\n"
        "     minimum extent necessary to make it enforceable. If the provision\n"
        "     cannot be reformed, it shall be severed from this Public License\n"
        "     without affecting the enforceability of the remaining terms and\n"
        "     conditions.\n"
        "\n"
        "  c. No term or condition of this Public License will be waived and no\n"
        "     failure to comply consented to unless expressly agreed to by the\n"
        "     Licensor.\n"
        "\n"
        "  d. Nothing in this Public License constitutes or may be interpreted\n"
        "     as a limitation upon, or waiver of, any privileges and immunities\n"
        "     that apply to the Licensor or You, including from the legal\n"
        "     processes of any jurisdiction or authority.\n"
        "\n"
        "\n"
        "=======================================================================\n"
        "\n"
        "Creative Commons is not a party to its public\n"
        "licenses. Notwithstanding, Creative Commons may elect to apply one of\n"
        "its public licenses to material it publishes and in those instances\n"
        "will be considered the \u201cLicensor.\u201d The text of the Creative Commons\n"
        "public licenses is dedicated to the public domain under the CC0 Public\n"
        "Domain Dedication. Except for the limited purpose of indicating that\n"
        "material is shared under a Creative Commons public license or as\n"
        "otherwise permitted by the Creative Commons policies published at\n"
        "creativecommons.org/policies, Creative Commons does not authorize the\n"
        "use of the trademark \"Creative Commons\" or any other trademark or logo\n"
        "of Creative Commons without its prior written consent including,\n"
        "without limitation, in connection with any unauthorized modifications\n"
        "to any of its public licenses or any other arrangements,\n"
        "understandings, or agreements concerning use of licensed material. For\n"
        "the avoidance of doubt, this paragraph does not form part of the\n"
        "public licenses.\n"
        "\n"
        "Creative Commons may be contacted at creativecommons.org.\n"
    ),
    "CC0-1.0": (
        "No full license-text file was found in the installed Windows output for this identifier. Marked "
        "UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: "
        "https://creativecommons.org/publicdomain/zero/1.0/.\n"
    ),
    "CNRI-Python": (
        "No full license-text file was found in the installed Windows output for this identifier. Marked "
        "UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: "
        "https://opensource.org/license/cnri-python.\n"
    ),
    "GCC-exception-3.1": (
        "No full license-text file was found in the installed Windows output for this identifier. Marked "
        "UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: "
        "https://www.gnu.org/licenses/gcc-exception-3.1.html.\n"
    ),
    "ISC": (
        "Copyright 2010-2023 Mike Bostock\n"
        "\n"
        "Permission to use, copy, modify, and/or distribute this software for any purpose\n"
        "with or without fee is hereby granted, provided that the above copyright notice\n"
        "and this permission notice appear in all copies.\n"
        "\n"
        "THE SOFTWARE IS PROVIDED \"AS IS\" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH\n"
        "REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND\n"
        "FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,\n"
        "INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS\n"
        "OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER\n"
        "TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF\n"
        "THIS SOFTWARE.\n"
    ),
    "LGPL-2.1-or-later": (
        "No full license-text file was found in the installed Windows output for this identifier. Marked "
        "UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: "
        "https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html.\n"
    ),
    "LGPL-3.0-or-later": (
        "No full license-text file was found in the installed Windows output for this identifier. Marked "
        "UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: "
        "https://www.gnu.org/licenses/lgpl-3.0.html.\n"
    ),
    "MIT": (
        "MIT License\n"
        "\n"
        "Copyright (c) Meta Platforms, Inc. and affiliates.\n"
        "\n"
        "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
        "of this software and associated documentation files (the \"Software\"), to deal\n"
        "in the Software without restriction, including without limitation the rights\n"
        "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n"
        "copies of the Software, and to permit persons to whom the Software is\n"
        "furnished to do so, subject to the following conditions:\n"
        "\n"
        "The above copyright notice and this permission notice shall be included in all\n"
        "copies or substantial portions of the Software.\n"
        "\n"
        "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n"
        "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n"
        "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n"
        "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n"
        "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n"
        "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\n"
        "SOFTWARE.\n"
    ),
    "MIT-0": (
        "No full license-text file was found in the installed Windows output for this identifier. Marked "
        "UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: "
        "https://opensource.org/license/mit-0.\n"
    ),
    "MPL-2.0": (
        "Mozilla Public License Version 2.0\n"
        "==================================\n"
        "\n"
        "1. Definitions\n"
        "--------------\n"
        "\n"
        "1.1. \"Contributor\"\n"
        "    means each individual or legal entity that creates, contributes to\n"
        "    the creation of, or owns Covered Software.\n"
        "\n"
        "1.2. \"Contributor Version\"\n"
        "    means the combination of the Contributions of others (if any) used\n"
        "    by a Contributor and that particular Contributor's Contribution.\n"
        "\n"
        "1.3. \"Contribution\"\n"
        "    means Covered Software of a particular Contributor.\n"
        "\n"
        "1.4. \"Covered Software\"\n"
        "    means Source Code Form to which the initial Contributor has attached\n"
        "    the notice in Exhibit A, the Executable Form of such Source Code\n"
        "    Form, and Modifications of such Source Code Form, in each case\n"
        "    including portions thereof.\n"
        "\n"
        "1.5. \"Incompatible With Secondary Licenses\"\n"
        "    means\n"
        "\n"
        "    (a) that the initial Contributor has attached the notice described\n"
        "        in Exhibit B to the Covered Software; or\n"
        "\n"
        "    (b) that the Covered Software was made available under the terms of\n"
        "        version 1.1 or earlier of the License, but not also under the\n"
        "        terms of a Secondary License.\n"
        "\n"
        "1.6. \"Executable Form\"\n"
        "    means any form of the work other than Source Code Form.\n"
        "\n"
        "1.7. \"Larger Work\"\n"
        "    means a work that combines Covered Software with other material, in \n"
        "    a separate file or files, that is not Covered Software.\n"
        "\n"
        "1.8. \"License\"\n"
        "    means this document.\n"
        "\n"
        "1.9. \"Licensable\"\n"
        "    means having the right to grant, to the maximum extent possible,\n"
        "    whether at the time of the initial grant or subsequently, any and\n"
        "    all of the rights conveyed by this License.\n"
        "\n"
        "1.10. \"Modifications\"\n"
        "    means any of the following:\n"
        "\n"
        "    (a) any file in Source Code Form that results from an addition to,\n"
        "        deletion from, or modification of the contents of Covered\n"
        "        Software; or\n"
        "\n"
        "    (b) any new file in Source Code Form that contains any Covered\n"
        "        Software.\n"
        "\n"
        "1.11. \"Patent Claims\" of a Contributor\n"
        "    means any patent claim(s), including without limitation, method,\n"
        "    process, and apparatus claims, in any patent Licensable by such\n"
        "    Contributor that would be infringed, but for the grant of the\n"
        "    License, by the making, using, selling, offering for sale, having\n"
        "    made, import, or transfer of either its Contributions or its\n"
        "    Contributor Version.\n"
        "\n"
        "1.12. \"Secondary License\"\n"
        "    means either the GNU General Public License, Version 2.0, the GNU\n"
        "    Lesser General Public License, Version 2.1, the GNU Affero General\n"
        "    Public License, Version 3.0, or any later versions of those\n"
        "    licenses.\n"
        "\n"
        "1.13. \"Source Code Form\"\n"
        "    means the form of the work preferred for making modifications.\n"
        "\n"
        "1.14. \"You\" (or \"Your\")\n"
        "    means an individual or a legal entity exercising rights under this\n"
        "    License. For legal entities, \"You\" includes any entity that\n"
        "    controls, is controlled by, or is under common control with You. For\n"
        "    purposes of this definition, \"control\" means (a) the power, direct\n"
        "    or indirect, to cause the direction or management of such entity,\n"
        "    whether by contract or otherwise, or (b) ownership of more than\n"
        "    fifty percent (50%) of the outstanding shares or beneficial\n"
        "    ownership of such entity.\n"
        "\n"
        "2. License Grants and Conditions\n"
        "--------------------------------\n"
        "\n"
        "2.1. Grants\n"
        "\n"
        "Each Contributor hereby grants You a world-wide, royalty-free,\n"
        "non-exclusive license:\n"
        "\n"
        "(a) under intellectual property rights (other than patent or trademark)\n"
        "    Licensable by such Contributor to use, reproduce, make available,\n"
        "    modify, display, perform, distribute, and otherwise exploit its\n"
        "    Contributions, either on an unmodified basis, with Modifications, or\n"
        "    as part of a Larger Work; and\n"
        "\n"
        "(b) under Patent Claims of such Contributor to make, use, sell, offer\n"
        "    for sale, have made, import, and otherwise transfer either its\n"
        "    Contributions or its Contributor Version.\n"
        "\n"
        "2.2. Effective Date\n"
        "\n"
        "The licenses granted in Section 2.1 with respect to any Contribution\n"
        "become effective for each Contribution on the date the Contributor first\n"
        "distributes such Contribution.\n"
        "\n"
        "2.3. Limitations on Grant Scope\n"
        "\n"
        "The licenses granted in this Section 2 are the only rights granted under\n"
        "this License. No additional rights or licenses will be implied from the\n"
        "distribution or licensing of Covered Software under this License.\n"
        "Notwithstanding Section 2.1(b) above, no patent license is granted by a\n"
        "Contributor:\n"
        "\n"
        "(a) for any code that a Contributor has removed from Covered Software;\n"
        "    or\n"
        "\n"
        "(b) for infringements caused by: (i) Your and any other third party's\n"
        "    modifications of Covered Software, or (ii) the combination of its\n"
        "    Contributions with other software (except as part of its Contributor\n"
        "    Version); or\n"
        "\n"
        "(c) under Patent Claims infringed by Covered Software in the absence of\n"
        "    its Contributions.\n"
        "\n"
        "This License does not grant any rights in the trademarks, service marks,\n"
        "or logos of any Contributor (except as may be necessary to comply with\n"
        "the notice requirements in Section 3.4).\n"
        "\n"
        "2.4. Subsequent Licenses\n"
        "\n"
        "No Contributor makes additional grants as a result of Your choice to\n"
        "distribute the Covered Software under a subsequent version of this\n"
        "License (see Section 10.2) or under the terms of a Secondary License (if\n"
        "permitted under the terms of Section 3.3).\n"
        "\n"
        "2.5. Representation\n"
        "\n"
        "Each Contributor represents that the Contributor believes its\n"
        "Contributions are its original creation(s) or it has sufficient rights\n"
        "to grant the rights to its Contributions conveyed by this License.\n"
        "\n"
        "2.6. Fair Use\n"
        "\n"
        "This License is not intended to limit any rights You have under\n"
        "applicable copyright doctrines of fair use, fair dealing, or other\n"
        "equivalents.\n"
        "\n"
        "2.7. Conditions\n"
        "\n"
        "Sections 3.1, 3.2, 3.3, and 3.4 are conditions of the licenses granted\n"
        "in Section 2.1.\n"
        "\n"
        "3. Responsibilities\n"
        "-------------------\n"
        "\n"
        "3.1. Distribution of Source Form\n"
        "\n"
        "All distribution of Covered Software in Source Code Form, including any\n"
        "Modifications that You create or to which You contribute, must be under\n"
        "the terms of this License. You must inform recipients that the Source\n"
        "Code Form of the Covered Software is governed by the terms of this\n"
        "License, and how they can obtain a copy of this License. You may not\n"
        "attempt to alter or restrict the recipients' rights in the Source Code\n"
        "Form.\n"
        "\n"
        "3.2. Distribution of Executable Form\n"
        "\n"
        "If You distribute Covered Software in Executable Form then:\n"
        "\n"
        "(a) such Covered Software must also be made available in Source Code\n"
        "    Form, as described in Section 3.1, and You must inform recipients of\n"
        "    the Executable Form how they can obtain a copy of such Source Code\n"
        "    Form by reasonable means in a timely manner, at a charge no more\n"
        "    than the cost of distribution to the recipient; and\n"
        "\n"
        "(b) You may distribute such Executable Form under the terms of this\n"
        "    License, or sublicense it under different terms, provided that the\n"
        "    license for the Executable Form does not attempt to limit or alter\n"
        "    the recipients' rights in the Source Code Form under this License.\n"
        "\n"
        "3.3. Distribution of a Larger Work\n"
        "\n"
        "You may create and distribute a Larger Work under terms of Your choice,\n"
        "provided that You also comply with the requirements of this License for\n"
        "the Covered Software. If the Larger Work is a combination of Covered\n"
        "Software with a work governed by one or more Secondary Licenses, and the\n"
        "Covered Software is not Incompatible With Secondary Licenses, this\n"
        "License permits You to additionally distribute such Covered Software\n"
        "under the terms of such Secondary License(s), so that the recipient of\n"
        "the Larger Work may, at their option, further distribute the Covered\n"
        "Software under the terms of either this License or such Secondary\n"
        "License(s).\n"
        "\n"
        "3.4. Notices\n"
        "\n"
        "You may not remove or alter the substance of any license notices\n"
        "(including copyright notices, patent notices, disclaimers of warranty,\n"
        "or limitations of liability) contained within the Source Code Form of\n"
        "the Covered Software, except that You may alter any license notices to\n"
        "the extent required to remedy known factual inaccuracies.\n"
        "\n"
        "3.5. Application of Additional Terms\n"
        "\n"
        "You may choose to offer, and to charge a fee for, warranty, support,\n"
        "indemnity or liability obligations to one or more recipients of Covered\n"
        "Software. However, You may do so only on Your own behalf, and not on\n"
        "behalf of any Contributor. You must make it absolutely clear that any\n"
        "such warranty, support, indemnity, or liability obligation is offered by\n"
        "You alone, and You hereby agree to indemnify every Contributor for any\n"
        "liability incurred by such Contributor as a result of warranty, support,\n"
        "indemnity or liability terms You offer. You may include additional\n"
        "disclaimers of warranty and limitations of liability specific to any\n"
        "jurisdiction.\n"
        "\n"
        "4. Inability to Comply Due to Statute or Regulation\n"
        "---------------------------------------------------\n"
        "\n"
        "If it is impossible for You to comply with any of the terms of this\n"
        "License with respect to some or all of the Covered Software due to\n"
        "statute, judicial order, or regulation then You must: (a) comply with\n"
        "the terms of this License to the maximum extent possible; and (b)\n"
        "describe the limitations and the code they affect. Such description must\n"
        "be placed in a text file included with all distributions of the Covered\n"
        "Software under this License. Except to the extent prohibited by statute\n"
        "or regulation, such description must be sufficiently detailed for a\n"
        "recipient of ordinary skill to be able to understand it.\n"
        "\n"
        "5. Termination\n"
        "--------------\n"
        "\n"
        "5.1. The rights granted under this License will terminate automatically\n"
        "if You fail to comply with any of its terms. However, if You become\n"
        "compliant, then the rights granted under this License from a particular\n"
        "Contributor are reinstated (a) provisionally, unless and until such\n"
        "Contributor explicitly and finally terminates Your grants, and (b) on an\n"
        "ongoing basis, if such Contributor fails to notify You of the\n"
        "non-compliance by some reasonable means prior to 60 days after You have\n"
        "come back into compliance. Moreover, Your grants from a particular\n"
        "Contributor are reinstated on an ongoing basis if such Contributor\n"
        "notifies You of the non-compliance by some reasonable means, this is the\n"
        "first time You have received notice of non-compliance with this License\n"
        "from such Contributor, and You become compliant prior to 30 days after\n"
        "Your receipt of the notice.\n"
        "\n"
        "5.2. If You initiate litigation against any entity by asserting a patent\n"
        "infringement claim (excluding declaratory judgment actions,\n"
        "counter-claims, and cross-claims) alleging that a Contributor Version\n"
        "directly or indirectly infringes any patent, then the rights granted to\n"
        "You by any and all Contributors for the Covered Software under Section\n"
        "2.1 of this License shall terminate.\n"
        "\n"
        "5.3. In the event of termination under Sections 5.1 or 5.2 above, all\n"
        "end user license agreements (excluding distributors and resellers) which\n"
        "have been validly granted by You or Your distributors under this License\n"
        "prior to termination shall survive termination.\n"
        "\n"
        "************************************************************************\n"
        "*                                                                      *\n"
        "*  6. Disclaimer of Warranty                                           *\n"
        "*  -------------------------                                           *\n"
        "*                                                                      *\n"
        "*  Covered Software is provided under this License on an \"as is\"       *\n"
        "*  basis, without warranty of any kind, either expressed, implied, or  *\n"
        "*  statutory, including, without limitation, warranties that the       *\n"
        "*  Covered Software is free of defects, merchantable, fit for a        *\n"
        "*  particular purpose or non-infringing. The entire risk as to the     *\n"
        "*  quality and performance of the Covered Software is with You.        *\n"
        "*  Should any Covered Software prove defective in any respect, You     *\n"
        "*  (not any Contributor) assume the cost of any necessary servicing,   *\n"
        "*  repair, or correction. This disclaimer of warranty constitutes an   *\n"
        "*  essential part of this License. No use of any Covered Software is   *\n"
        "*  authorized under this License except under this disclaimer.         *\n"
        "*                                                                      *\n"
        "************************************************************************\n"
        "\n"
        "************************************************************************\n"
        "*                                                                      *\n"
        "*  7. Limitation of Liability                                          *\n"
        "*  --------------------------                                          *\n"
        "*                                                                      *\n"
        "*  Under no circumstances and under no legal theory, whether tort      *\n"
        "*  (including negligence), contract, or otherwise, shall any           *\n"
        "*  Contributor, or anyone who distributes Covered Software as          *\n"
        "*  permitted above, be liable to You for any direct, indirect,         *\n"
        "*  special, incidental, or consequential damages of any character      *\n"
        "*  including, without limitation, damages for lost profits, loss of    *\n"
        "*  goodwill, work stoppage, computer failure or malfunction, or any    *\n"
        "*  and all other commercial damages or losses, even if such party      *\n"
        "*  shall have been informed of the possibility of such damages. This   *\n"
        "*  limitation of liability shall not apply to liability for death or   *\n"
        "*  personal injury resulting from such party's negligence to the       *\n"
        "*  extent applicable law prohibits such limitation. Some               *\n"
        "*  jurisdictions do not allow the exclusion or limitation of           *\n"
        "*  incidental or consequential damages, so this exclusion and          *\n"
        "*  limitation may not apply to You.                                    *\n"
        "*                                                                      *\n"
        "************************************************************************\n"
        "\n"
        "8. Litigation\n"
        "-------------\n"
        "\n"
        "Any litigation relating to this License may be brought only in the\n"
        "courts of a jurisdiction where the defendant maintains its principal\n"
        "place of business and such litigation shall be governed by laws of that\n"
        "jurisdiction, without reference to its conflict-of-law provisions.\n"
        "Nothing in this Section shall prevent a party's ability to bring\n"
        "cross-claims or counter-claims.\n"
        "\n"
        "9. Miscellaneous\n"
        "----------------\n"
        "\n"
        "This License represents the complete agreement concerning the subject\n"
        "matter hereof. If any provision of this License is held to be\n"
        "unenforceable, such provision shall be reformed only to the extent\n"
        "necessary to make it enforceable. Any law or regulation which provides\n"
        "that the language of a contract shall be construed against the drafter\n"
        "shall not be used to construe this License against a Contributor.\n"
        "\n"
        "10. Versions of the License\n"
        "---------------------------\n"
        "\n"
        "10.1. New Versions\n"
        "\n"
        "Mozilla Foundation is the license steward. Except as provided in Section\n"
        "10.3, no one other than the license steward has the right to modify or\n"
        "publish new versions of this License. Each version will be given a\n"
        "distinguishing version number.\n"
        "\n"
        "10.2. Effect of New Versions\n"
        "\n"
        "You may distribute the Covered Software under the terms of the version\n"
        "of the License under which You originally received the Covered Software,\n"
        "or under the terms of any subsequent version published by the license\n"
        "steward.\n"
        "\n"
        "10.3. Modified Versions\n"
        "\n"
        "If you create software not governed by this License, and you want to\n"
        "create a new license for such software, you may create and use a\n"
        "modified version of this License if you rename the license and remove\n"
        "any references to the name of the license steward (except to note that\n"
        "such modified license differs from this License).\n"
        "\n"
        "10.4. Distributing Source Code Form that is Incompatible With Secondary\n"
        "Licenses\n"
        "\n"
        "If You choose to distribute Source Code Form that is Incompatible With\n"
        "Secondary Licenses under the terms of this version of the License, the\n"
        "notice described in Exhibit B of this License must be attached.\n"
        "\n"
        "Exhibit A - Source Code Form License Notice\n"
        "-------------------------------------------\n"
        "\n"
        "  This Source Code Form is subject to the terms of the Mozilla Public\n"
        "  License, v. 2.0. If a copy of the MPL was not distributed with this\n"
        "  file, You can obtain one at http://mozilla.org/MPL/2.0/.\n"
        "\n"
        "If it is not possible or desirable to put the notice in a particular\n"
        "file, then You may include the notice in a location (such as a LICENSE\n"
        "file in a relevant directory) where a recipient would be likely to look\n"
        "for such a notice.\n"
        "\n"
        "You may add additional accurate notices of copyright ownership.\n"
        "\n"
        "Exhibit B - \"Incompatible With Secondary Licenses\" Notice\n"
        "---------------------------------------------------------\n"
        "\n"
        "  This Source Code Form is \"Incompatible With Secondary Licenses\", as\n"
        "  defined by the Mozilla Public License, v. 2.0.\n"
    ),
    "MSVC-Redistrib": (
        "No full license-text file was found in the installed Windows output for this identifier. Marked "
        "UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: "
        "https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170.\n"
    ),
    "NVIDIA-Proprietary": (
        "No full license-text file was found in the installed Windows output for this identifier. Marked "
        "UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: "
        "https://docs.nvidia.com/cuda/eula/index.html.\n"
    ),
    "OFL-1.1": (
        "SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007\n"
        "-----------------------------------------------------------\n"
        "\n"
        "PREAMBLE\n"
        "The goals of the Open Font License (OFL) are to stimulate worldwide\n"
        "development of collaborative font projects, to support the font creation\n"
        "efforts of academic and linguistic communities, and to provide a free and\n"
        "open framework in which fonts may be shared and improved in partnership\n"
        "with others.\n"
        "\n"
        "The OFL allows the licensed fonts to be used, studied, modified and\n"
        "redistributed freely as long as they are not sold by themselves. The\n"
        "fonts, including any derivative works, can be bundled, embedded, \n"
        "redistributed and/or sold with any software provided that any reserved\n"
        "names are not used by derivative works. The fonts and derivatives,\n"
        "however, cannot be released under any other type of license. The\n"
        "requirement for fonts to remain under this license does not apply\n"
        "to any document created using the fonts or their derivatives.\n"
        "\n"
        "DEFINITIONS\n"
        "\"Font Software\" refers to the set of files released by the Copyright\n"
        "Holder(s) under this license and clearly marked as such. This may\n"
        "include source files, build scripts and documentation.\n"
        "\n"
        "\"Reserved Font Name\" refers to any names specified as such after the\n"
        "copyright statement(s).\n"
        "\n"
        "\"Original Version\" refers to the collection of Font Software components as\n"
        "distributed by the Copyright Holder(s).\n"
        "\n"
        "\"Modified Version\" refers to any derivative made by adding to, deleting,\n"
        "or substituting -- in part or in whole -- any of the components of the\n"
        "Original Version, by changing formats or by porting the Font Software to a\n"
        "new environment.\n"
        "\n"
        "\"Author\" refers to any designer, engineer, programmer, technical\n"
        "writer or other person who contributed to the Font Software.\n"
        "\n"
        "PERMISSION & CONDITIONS\n"
        "Permission is hereby granted, free of charge, to any person obtaining\n"
        "a copy of the Font Software, to use, study, copy, merge, embed, modify,\n"
        "redistribute, and sell modified and unmodified copies of the Font\n"
        "Software, subject to the following conditions:\n"
        "\n"
        "1) Neither the Font Software nor any of its individual components,\n"
        "in Original or Modified Versions, may be sold by itself.\n"
        "\n"
        "2) Original or Modified Versions of the Font Software may be bundled,\n"
        "redistributed and/or sold with any software, provided that each copy\n"
        "contains the above copyright notice and this license. These can be\n"
        "included either as stand-alone text files, human-readable headers or\n"
        "in the appropriate machine-readable metadata fields within text or\n"
        "binary files as long as those fields can be easily viewed by the user.\n"
        "\n"
        "3) No Modified Version of the Font Software may use the Reserved Font\n"
        "Name(s) unless explicit written permission is granted by the corresponding\n"
        "Copyright Holder. This restriction only applies to the primary font name as\n"
        "presented to the users.\n"
        "\n"
        "4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font\n"
        "Software shall not be used to promote, endorse or advertise any\n"
        "Modified Version, except to acknowledge the contribution(s) of the\n"
        "Copyright Holder(s) and the Author(s) or with their explicit written\n"
        "permission.\n"
        "\n"
        "5) The Font Software, modified or unmodified, in part or in whole,\n"
        "must be distributed entirely under this license, and must not be\n"
        "distributed under any other license. The requirement for fonts to\n"
        "remain under this license does not apply to any document created\n"
        "using the Font Software.\n"
        "\n"
        "TERMINATION\n"
        "This license becomes null and void if any of the above conditions are\n"
        "not met.\n"
        "\n"
        "DISCLAIMER\n"
        "THE FONT SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND,\n"
        "EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF\n"
        "MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT\n"
        "OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE\n"
        "COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,\n"
        "INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL\n"
        "DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING\n"
        "FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM\n"
        "OTHER DEALINGS IN THE FONT SOFTWARE.\n"
    ),
    "PSF-2.0": (
        "No full license-text file was found in the installed Windows output for this identifier. Marked "
        "UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: "
        "https://docs.python.org/3/license.html.\n"
    ),
    "PolyForm-Strict-1.0.0": (
        "No full license-text file was found in the installed Windows output for this identifier. Marked "
        "UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: "
        "https://polyformproject.org/licenses/strict/1.0.0/.\n"
    ),
    "PortAudio-MIT": (
        "No full license-text file was found in the installed Windows output for this identifier. Marked "
        "UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: "
        "https://portaudio.com/license.html.\n"
    ),
    "UNVERIFIED": (
        "No full license-text file was found in the installed Windows output for this identifier. Marked "
        "UNVERIFIED where local evidence is absent; no legal conclusion.\n"
    ),
    "Unicode-3.0": (
        "UNICODE LICENSE V3\n"
        "\n"
        "COPYRIGHT AND PERMISSION NOTICE\n"
        "\n"
        "Copyright \u00a9 2020-2024 Unicode, Inc.\n"
        "\n"
        "NOTICE TO USER: Carefully read the following legal agreement. BY\n"
        "DOWNLOADING, INSTALLING, COPYING OR OTHERWISE USING DATA FILES, AND/OR\n"
        "SOFTWARE, YOU UNEQUIVOCALLY ACCEPT, AND AGREE TO BE BOUND BY, ALL OF THE\n"
        "TERMS AND CONDITIONS OF THIS AGREEMENT. IF YOU DO NOT AGREE, DO NOT\n"
        "DOWNLOAD, INSTALL, COPY, DISTRIBUTE OR USE THE DATA FILES OR SOFTWARE.\n"
        "\n"
        "Permission is hereby granted, free of charge, to any person obtaining a\n"
        "copy of data files and any associated documentation (the \"Data Files\") or\n"
        "software and any associated documentation (the \"Software\") to deal in the\n"
        "Data Files or Software without restriction, including without limitation\n"
        "the rights to use, copy, modify, merge, publish, distribute, and/or sell\n"
        "copies of the Data Files or Software, and to permit persons to whom the\n"
        "Data Files or Software are furnished to do so, provided that either (a)\n"
        "this copyright and permission notice appear with all copies of the Data\n"
        "Files or Software, or (b) this copyright and permission notice appear in\n"
        "associated Documentation.\n"
        "\n"
        "THE DATA FILES AND SOFTWARE ARE PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY\n"
        "KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF\n"
        "MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT OF\n"
        "THIRD PARTY RIGHTS.\n"
        "\n"
        "IN NO EVENT SHALL THE COPYRIGHT HOLDER OR HOLDERS INCLUDED IN THIS NOTICE\n"
        "BE LIABLE FOR ANY CLAIM, OR ANY SPECIAL INDIRECT OR CONSEQUENTIAL DAMAGES,\n"
        "OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,\n"
        "WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION,\n"
        "ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THE DATA\n"
        "FILES OR SOFTWARE.\n"
        "\n"
        "Except as contained in this notice, the name of a copyright holder shall\n"
        "not be used in advertising or otherwise to promote the sale, use or other\n"
        "dealings in these Data Files or Software without prior written\n"
        "authorization of the copyright holder.\n"
        "\n"
        "SPDX-License-Identifier: Unicode-3.0\n"
        "\n"
        "\u2014\n"
        "\n"
        "Portions of ICU4X may have been adapted from ICU4C and/or ICU4J.\n"
        "ICU 1.8.1 to ICU 57.1 \u00a9 1995-2016 International Business Machines Corporation and others.\n"
    ),
    "Unlicense": (
        "No full license-text file was found in the installed Windows output for this identifier. Marked "
        "UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: "
        "https://unlicense.org/.\n"
    ),
    "Zlib": (
        "No full license-text file was found in the installed Windows output for this identifier. Marked "
        "UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: "
        "https://opensource.org/license/zlib.\n"
    ),
}

class Component(NamedTuple):
    name: str
    version: str
    license_id: str
    copyright: str
    group: str
    status: str = "VERIFIED"
    detail: str = ""


# Checked-in manifest of components observed in the Windows installer output.
# Identifiers are quoted verbatim from dist-info / audit evidence; "UNVERIFIED"
# means the local artifact carried no licence file. No legal conclusions.
COMPONENTS: tuple[Component, ...] = (
    Component(
            "Lausu (this project)",
            "1.0.0",
            "PolyForm Strict License 1.0.0",
            "Copyright 2026 Abdallah IsDev",
            "PolyForm-Strict-1.0.0",
            detail="Own project; root LICENSE is authoritative. METADATA says MIT but the LICENSE file says "
        "PolyForm Strict 1.0.0 \u2014 contradiction quoted verbatim, no conclusion.",
    ),
    Component(
            "Tauri host crate graph",
            "per Cargo.lock",
            "mixed (MIT, Apache-2.0, Unicode-3.0, MPL-2.0, CC0-1.0, Zlib, BSL-1.0, ISC)",
            "",
            "MIT",
            detail="Root crate license-file = ../LICENSE (PolyForm Strict 1.0.0). Representative: unicode-ident "
        "'(MIT OR Apache-2.0) AND Unicode-3.0'; icu_* 2.2.0 'Unicode-3.0'; "
        "cssparser/selectors/option-ext/dtoa-short 'MPL-2.0'; ryu 'Apache-2.0 OR BSL-1.0'; dunce "
        "'CC0-1.0 OR MIT-0 OR Apache-2.0'; foldhash 'Zlib'.",
    ),
    Component(
            "windows-key-listener.exe",
            "source build",
            "PolyForm Strict License 1.0.0",
            "Copyright 2026 Abdallah IsDev",
            "PolyForm-Strict-1.0.0",
            detail="Compiled from voice_typer/server/native/windows-key-listener.c in this repository.",
    ),
    Component(
            "av (PyAV)",
            "17.1.0",
            "BSD-3-Clause",
            "Copyright retained by original committers.",
            "BSD-3-Clause",
            detail="Wheel cp311-abi3-win_amd64; bundled av.libs DLLs report verbatim 'LGPL version 3 or later'. "
        "Full facts in the hand-written PyAV section.",
    ),
    Component(
            "certifi",
            "2026.10.19",
            "MPL-2.0",
            "",
            "MPL-2.0",
            "UNVERIFIED",
            detail="Shipped; MPL notice text not present in the installed output. Upstream "
        "https://github.com/certifi/python-certifi",
    ),
    Component(
            "charset-normalizer",
            "3.5.1",
            "MIT",
            "Copyright (c) 2025 TAHRI Ahmed R.",
            "MIT",
    ),
    Component(
            "cryptography",
            "50.0.0",
            "Apache-2.0 OR BSD-3-Clause",
            "",
            "Apache-2.0",
            detail="Dual licensed; both identifiers quoted verbatim.",
    ),
    Component(
            "hf-xet",
            "1.6.0",
            "Apache-2.0",
            "",
            "Apache-2.0",
    ),
    Component(
            "MarkupSafe",
            "3.0.3",
            "BSD-3-Clause",
            "",
            "BSD-3-Clause",
    ),
    Component(
            "numpy",
            "2.5.2",
            "BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0",
            "Copyright (c) 2005-2025, NumPy Developers.",
            "BSD-3-Clause",
            detail="OpenBLAS DLLs carry 'GPL-3.0-or-later WITH GCC-exception-3.1'; text not shipped.",
    ),
    Component(
            "onnxruntime",
            "1.29.0 (installed metadata); shipped DLL 1.28.0",
            "MIT License",
            "Copyright (c) Microsoft Corporation",
            "MIT",
            detail="Build drift: shipped onnxruntime.dll PE version 1.28.0; dist-info 1.29.0. ThirdPartyNotices not "
        "shipped.",
    ),
    Component(
            "pillow",
            "13.0.0",
            "MIT-CMU",
            "",
            "MIT",
    ),
    Component(
            "psutil",
            "7.2.2",
            "BSD-3-Clause",
            "",
            "BSD-3-Clause",
    ),
    Component(
            "pydantic-core",
            "unknown",
            "UNVERIFIED",
            "",
            "UNVERIFIED",
            "UNVERIFIED",
            detail="No installed dist-info; upstream hint only https://github.com/pydantic/pydantic-core",
    ),
    Component(
            "PyYAML",
            "6.0.3",
            "MIT",
            "Copyright (c) 2017-2021 Ingy d\u00f6t Net",
            "MIT",
    ),
    Component(
            "regex",
            "2026.7.19",
            "Apache-2.0 AND CNRI-Python",
            "",
            "Apache-2.0",
    ),
    Component(
            "requests",
            "2.34.2",
            "Apache-2.0",
            "",
            "Apache-2.0",
    ),
    Component(
            "scipy",
            "1.18.0",
            "BSD-3-Clause",
            "Copyright (c) 2001-2002 Enthought, Inc. 2003, SciPy Developers.",
            "BSD-3-Clause",
    ),
    Component(
            "sounddevice",
            "0.5.6",
            "MIT",
            "Copyright (c) 2015-2025 Matthias Geier",
            "MIT",
    ),
    Component(
            "soundfile",
            "0.14.0",
            "BSD 3-Clause License",
            "Copyright (c) 2013, Bastian Bechtold",
            "BSD-3-Clause",
    ),
    Component(
            "tokenizers",
            "0.23.1",
            "Apache-2.0",
            "",
            "Apache-2.0",
    ),
    Component(
            "tzdata",
            "unknown",
            "UNVERIFIED",
            "",
            "UNVERIFIED",
            "UNVERIFIED",
            detail="No local version evidence in the installed output.",
    ),
    Component(
            "websockets",
            "13.1",
            "BSD-3-Clause",
            "Copyright (c) Aymeric Augustin and contributors",
            "BSD-3-Clause",
    ),
    Component(
            "wrapt",
            "2.3.0",
            "BSD-2-Clause",
            "",
            "BSD-2-Clause",
    ),
    Component(
            "zstandard",
            "unknown",
            "UNVERIFIED",
            "",
            "UNVERIFIED",
            "UNVERIFIED",
            detail="Upstream hint only https://github.com/facebook/zstd",
    ),
    Component(
            "yt-dlp",
            "2026.8.19",
            "Unlicense",
            "",
            "Unlicense",
    ),
    Component(
            "yt-dlp-ejs",
            "unknown",
            "Unlicense AND MIT AND ISC",
            "",
            "Unlicense",
            detail="Bundles meriyah (ISC) and astring (MIT).",
    ),
    Component(
            "huggingface_hub",
            "1.28.0",
            "Apache-2.0",
            "",
            "Apache-2.0",
    ),
    Component(
            "libsndfile_x64.dll",
            "unknown",
            "LGPL-2.1-or-later",
            "",
            "LGPL-2.1-or-later",
            "UNVERIFIED",
            detail="PRESENT in onefile cache; no licence file shipped. Local .venv COPYING: 'GNU LESSER GENERAL "
        "PUBLIC LICENSE Version 2.1, February 1999'.",
    ),
    Component(
            "PortAudio (libportaudio64bit.dll, libportaudio64bit-asio.dll)",
            "unknown",
            "PortAudio MIT-style",
            "Copyright (c) 1999-2011 Ross Bencina and Phil Burk",
            "PortAudio-MIT",
            "UNVERIFIED",
            detail="PRESENT; no licence file shipped. Upstream https://portaudio.com/license.html",
    ),
    Component(
            "libffi-8.dll",
            "unknown",
            "MIT (upstream only)",
            "",
            "UNVERIFIED",
            "UNVERIFIED",
            detail="PRESENT; no version resource. Upstream https://github.com/libffi/libffi/blob/master/LICENSE",
    ),
    Component(
            "CPython runtime (python312.dll, python3.dll, stdlib .pyd)",
            "3.12.10",
            "PSF-2.0",
            "Python Software Foundation",
            "PSF-2.0",
            "UNVERIFIED",
            detail="PRESENT; PE 3.12.10 differs from dev .venv 3.13.7; no licence file shipped. Upstream "
        "https://docs.python.org/3/license.html",
    ),
    Component(
            "OpenSSL (libcrypto-3.dll, libssl-3.dll)",
            "3.0.16",
            "Apache-2.0",
            "The OpenSSL Toolkit",
            "Apache-2.0",
            "UNVERIFIED",
            detail="PRESENT; Apache-2.0 NOTICE text not shipped. Upstream "
        "https://www.openssl.org/source/license.html",
    ),
    Component(
            "MSVC runtime (vcruntime140.dll, vcruntime140_1.dll)",
            "unknown",
            "Microsoft Software License Terms",
            "",
            "MSVC-Redistrib",
            "UNVERIFIED",
            detail="PRESENT; no licence file shipped. Upstream "
        "https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170",
    ),
    Component(
            "pywin32 binaries",
            "unknown (312 build tag)",
            "PSF-2.0 (upstream only)",
            "",
            "PSF-2.0",
            "UNVERIFIED",
            detail="PRESENT; no dist-info in dev venv. Upstream https://github.com/mhammond/pywin32",
    ),
    Component(
            "_pydantic_core.pyd",
            "unknown",
            "MIT (upstream only)",
            "",
            "UNVERIFIED",
            "UNVERIFIED",
            detail="PRESENT; no dist-info or licence text. Upstream https://github.com/pydantic/pydantic-core",
    ),
    Component(
            "zstandard _cffi.pyd / backend_c.pyd",
            "unknown",
            "BSD-3-Clause (upstream only)",
            "",
            "BSD-3-Clause",
            "UNVERIFIED",
            detail="PRESENT; no dist-info or licence text. Upstream https://github.com/facebook/zstd",
    ),
    Component(
            "OpenBLAS DLLs (numpy.libs, scipy.libs)",
            "unknown",
            "GPL-3.0-or-later WITH GCC-exception-3.1",
            "Copyright (C) 2002-2017 Free Software Foundation, Inc.",
            "GCC-exception-3.1",
            "UNVERIFIED",
            detail="PRESENT; exception text not shipped; hash suffixes differ from .venv RECORD, provenance "
        "UNVERIFIED.",
    ),
    Component(
            "uninstall.exe (NSIS)",
            "unknown",
            "Common Public License version 1.0 + LZMA exception",
            "",
            "UNVERIFIED",
            "UNVERIFIED",
            detail="PRESENT; linked modules unverified.",
    ),
    Component(
            "FFmpeg (Windows x64, LGPL-only build)",
            "n9.0.2-61-gd59078794d-20261120",
            "LGPL-2.1-or-later (LGPL-only build configuration)",
            "Copyright (c) 2000-2026 the FFmpeg developers",
            "LGPL-2.1-or-later",
            detail="See dedicated FFmpeg section; manifest scripts/ffmpeg-lgpl-win64.json. No legal conclusion.",
    ),
    Component(
            "FFmpeg libraries in av.libs (25 DLLs)",
            "8.1.1",
            "LGPL version 3 or later",
            "Copyright (C) 2000-2026 FFmpeg Project",
            "LGPL-3.0-or-later",
            detail="Verbatim *_license() output; see PyAV section.",
    ),
    Component(
            "dpdfnet2.onnx",
            "revision dd6818d0",
            "Apache-2.0",
            "",
            "Apache-2.0",
            detail="Bundled 16 kHz streaming ONNX noise-suppression model.",
    ),
    Component(
            "gtcrn_simple.onnx",
            "unknown",
            "MIT",
            "",
            "MIT",
            detail="Bundled noise-suppression model with local MIT evidence.",
    ),
    Component(
            "silero_vad.onnx",
            "unknown",
            "MIT (upstream only)",
            "",
            "MIT",
            "UNVERIFIED",
            detail="PRESENT; no licence file beside the model. Upstream "
        "https://github.com/snakers4/silero-vad/blob/master/LICENSE",
    ),
    Component(
            "InterVariable.woff2 / InterVariable-Italic.woff2",
            "unknown",
            "OFL-1.1",
            "Copyright (c) 2016 The Inter Project Authors (https://github.com/rsms/inter)",
            "OFL-1.1",
            "UNVERIFIED",
            detail="Found in stale dist/; no local OFL.txt. Upstream https://scripts.sil.org/OFL",
    ),
    Component(
            "parakeet-tdt-0.6b-v3 / parakeet-tdt-0.6b-ultra-onnx",
            "unknown",
            "CC-BY-4.0",
            "",
            "CC-BY-4.0",
            "NOT-IN-INSTALLER",
            detail="Runtime download from Hugging Face, not in the Windows installer; listed for completeness.",
    ),
)


def _site_packages_dirs() -> list[Path]:
    """Local venv site-packages across Windows and POSIX layouts (read-only cross-check)."""
    return [VENV / "Lib" / "site-packages", *sorted((VENV / "lib").glob("python*/site-packages"))]


def read_installed_metadata() -> dict[str, tuple[str, str]]:
    """Read dist-info METADATA read-only; returns name -> (version, license)."""
    found: dict[str, tuple[str, str]] = {}
    dirs = [d for d in _site_packages_dirs() if d.is_dir()]
    if not dirs:
        return found
    for meta in sorted({m for d in dirs for m in d.glob("*.dist-info/METADATA")}):
        name = version = license_id = ""
        for line in meta.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Name:") and not name:
                name = line[5:].strip()
            elif line.startswith("Version:") and not version:
                version = line[8:].strip()
            elif (line.startswith("License-Expression:") or line.startswith("License:")) and not license_id:
                license_id = line.split(":", 1)[1].strip().strip('"')
        if name:
            found[name.lower().replace("_", "-")] = (version, license_id)
    return found


def _ancestors(scope: str):
    while True:
        yield scope
        if "/node_modules/" not in scope:
            break
        scope = scope.rsplit("/node_modules/", 1)[0]
    yield ""


def _resolve(packages: dict, scope: str, name: str) -> str | None:
    for parent in _ancestors(scope):
        key = f"{parent}/node_modules/{name}" if parent else f"node_modules/{name}"
        if key in packages:
            return key
    return None


def read_lockfiles() -> dict:
    """Read all three checked-in lockfiles read-only and derive stable facts."""
    requirements = set()
    for line in REQUIREMENTS_LOCK.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", line.strip())
        if m:
            requirements.add((m.group(1).lower(), m.group(2)))

    lock = json.loads(PACKAGE_LOCK.read_text(encoding="utf-8"))
    packages = lock["packages"]
    seen: set[str] = set()

    def walk(scope: str, entry: dict) -> None:
        deps = dict(entry.get("dependencies", {}))
        deps.update(entry.get("optionalDependencies", {}))
        deps.update(entry.get("peerDependencies", {}))
        for dep_name in deps:
            key = _resolve(packages, scope, dep_name)
            if key and key not in seen:
                seen.add(key)
                walk(key, packages[key])

    walk("", packages.get("", {}))
    npm = []
    for key in sorted(seen):
        info = packages[key]
        name = info.get("name") or key.rsplit("node_modules/", 1)[-1]
        npm.append((name, info.get("version", ""), info.get("license", "(none)")))
    npm_counts = dict(sorted(Counter(lic for _, _, lic in npm).items()))

    cargo_entries = len(
        re.findall(r"(?m)^\[\[package\]\]$", CARGO_LOCK.read_text(encoding="utf-8"))
    )
    return {
        "requirements": requirements,
        "npm": npm,
        "npm_counts": npm_counts,
        "cargo_entries": cargo_entries,
    }


def _table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    out.extend("| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |" for row in rows)
    return out


def render(facts: dict, metadata: dict) -> str:
    lines: list[str] = [BEGIN, "## Consolidated Windows-installer inventory (generated)", ""]
    lines += [
        "Regenerate with `python scripts/generate_third_party_notices.py` (`--check` verifies",
        "the committed artifact). Deterministic, offline, stdlib-only; no legal conclusions.",
        "The hand-written Lausu / yt-dlp / PyAV / FFmpeg / RNNoise / pystray / Deno / DPDFNet2",
        "sections outside these markers are preserved verbatim by regeneration.",
        "",
        "### Evidence and scope",
        "",
        "- Shipping is established from the Windows bundle config and the extracted",
        "  onefile/installed folders, NEVER from a lockfile alone.",
        f"- `requirements-lock.txt`: {len(facts['requirements'])} pinned distributions (read-only).",
        f"- `package-lock.json`: production closure of {len(facts['npm'])} packages "
        + "(licenses: "
        + ", ".join(f"{k} × {v}" for k, v in facts["npm_counts"].items())
        + ").",
        f"- `Cargo.lock`: {facts['cargo_entries']} package entries across all targets "
        "(Windows graph audited as 310 crates).",
        "- Installed dist-info metadata is a local cross-check only; its count depends on the "
        "machine and is deliberately omitted so this artifact is byte-identical on every OS.",
        "- Build drift is real: shipped python312.dll is 3.12.10 while dev .venv is 3.13.7;",
        "  shipped onnxruntime.dll is 1.28.0 while dist-info says 1.29.0. Local metadata never",
        "  overrides shipped-file evidence. UNVERIFIED means no local licence file was found.",
        "",
        "### Components grouped by license identifier",
        "",
    ]
    groups: dict[str, list[Component]] = {}
    for comp in COMPONENTS:
        groups.setdefault(comp.group, []).append(comp)
    for group in sorted(groups, key=lambda g: (g == "UNVERIFIED", g)):
        lines.append(f"#### {group}")
        lines.append("")
        lines += _table(
            ("Component", "Version", "License identifier (verbatim)", "Copyright", "Status"),
            [
                (c.name, c.version, c.license_id, c.copyright or "—", c.status)
                for c in sorted(groups[group], key=lambda c: c.name.lower())
            ],
        )
        lines.append("")
        for c in sorted(groups[group], key=lambda c: c.name.lower()):
            if c.detail:
                lines.append(f"- {c.name}: {c.detail}")
        if any(c.detail for c in groups[group]):
            lines.append("")

    lines += [
        "### npm production closure (from package-lock.json, read-only)",
        "",
        "All packages below are in the shipped renderer bundle. License identifiers are the",
        "verbatim `license` strings in `package-lock.json`; no GPL/LGPL/MPL/CC-BY appears in",
        "this closure.",
        "",
    ]
    lines += _table(("Package", "Version", "License identifier (verbatim)"), facts["npm"])
    lines.append("")

    lines += [
        "### License texts (one copy per distinct text)",
        "",
        "Each text below is emitted exactly once. Components reference it by the identifier",
        "heading above. For an identifier with no local full-text file, the entry is an explicit",
        "UNVERIFIED pointer with an upstream URL — never an invented legal body.",
        "",
    ]
    for key in sorted(LICENSE_TEXTS):
        lines.append(f"#### {key}")
        lines.append("")
        if key in FULL_TEXT_LICENSES:
            lines.append(f"Full text source: {TEXT_SOURCE[key]}. Component-specific copyrights are listed above.")
            lines.append("")
            lines.append("```text")
            lines.extend(LICENSE_TEXTS[key].rstrip("\n").split("\n"))
            lines.append("```")
        else:
            lines.append(LICENSE_TEXTS[key].rstrip())
        lines.append("")

    unverified = [c for c in COMPONENTS if c.status == "UNVERIFIED"]
    lines += [
        "### UNVERIFIED items (local evidence absent)",
        "",
        "Shipped-file statements come first; upstream facts are URL-labelled documentation and",
        "never override shipped-file evidence. No legal conclusion is made.",
        "",
    ]
    lines += _table(
        ("Component", "Shipped", "Reason / upstream documentation"),
        [
            (
                c.name,
                "PRESENT" if "PRESENT" in c.detail or "no licence file" in c.detail else "see above",
                c.detail,
            )
            for c in sorted(unverified, key=lambda c: c.name.lower())
        ],
    )
    lines += ["", END]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if the committed artifact is stale")
    parser.add_argument("--verbose", action="store_true", help="print metadata cross-check to stderr")
    args = parser.parse_args()

    metadata = read_installed_metadata()
    facts = read_lockfiles()
    if args.verbose:
        print(f"read {len(metadata)} installed distributions (indicative only)", file=sys.stderr)

    block = render(facts, metadata)
    current = NOTICE.read_text(encoding="utf-8")
    if BEGIN in current and END in current:
        head, rest = current.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        updated = head + block + tail.lstrip("\n")
    else:
        updated = current.rstrip("\n") + "\n\n" + block

    if args.check:
        if updated != current:
            print("generated notices are stale; run the generator", file=sys.stderr)
            return 1
        print("generated notices up to date")
        return 0

    if updated != current:
        NOTICE.write_text(updated, encoding="utf-8")
    print(
        f"wrote {NOTICE.relative_to(ROOT)}: {len(COMPONENTS)} catalog components, "
        f"{len(facts['npm'])} npm closure packages, "
        f"{len(groups_list())} license groups, {len(LICENSE_TEXTS)} license texts"
    )
    return 0


def groups_list() -> set[str]:
    return {c.group for c in COMPONENTS}


if __name__ == "__main__":
    raise SystemExit(main())
